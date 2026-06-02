"""
Adversarial Reviewer (upgraded) — deterministic-first routing over the IR.

The reviewer cross-references the verification layers and routes:
  APPROVED / REDESIGN(IR-node-keyed) / HALT.

Design choice: because L2 (solid inspector) already produces deterministic,
node-keyed pass/fail against the IR's *declared* claims, the DECISION is computed
deterministically here — this structurally guarantees "trust L2 over vision"
(L3) and makes the reviewer robust and testable with no network. An LLM
(`root_agent`) is kept for optional human-readable narration only; it can never
override the deterministic verdict.

On REDESIGN we emit a single, most-blocking, node+param repair instruction
(`recommendations_for_planner`) that the planner can apply to one IR node — the
key to convergence (vs. the legacy prose feedback that caused drift).

Information asymmetry is preserved: the reviewer sees check results and IR
intent, never raw kernel internals or generated code.
"""
from __future__ import annotations
import os
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "false")

import json
import uuid
import asyncio
import logging

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from core.model_config import get_model_name, safe_parse_json

# Severity order: pick the most fundamental failing claim first so repairs
# converge one node at a time.
_PRIORITY = ["no_interference", "single_solid", "contact", "concentric_alignment",
             "fit", "count", "bore_present", "bore_diameter_mm",
             "uniform_thickness_mm", "taper", "envelope_diameter_mm",
             "envelope_x_mm", "envelope_y_mm", "envelope_z_mm"]


def _repair_instruction(c: dict) -> str:
    """Map a failed L2 check to a surgical IR node+param edit."""
    node, claim = c["node"], c["claim"]
    exp, meas = c.get("expected"), c.get("measured")
    if claim == "single_solid":
        return ("Geometry is not one connected solid. Make sub-features OVERLAP "
                "their parent (embed 1–2mm, not just touch) so the boolean fuses "
                "into a single manifold. Do not change feature counts or sizes.")
    if claim == "count":
        return (f"Set `{node}.params.count = {exp}` (measured {meas}). "
                f"Do not change the per-instance feature geometry.")
    if claim in ("bore_present", "bore_diameter_mm"):
        return (f"`{node}` bore is wrong (measured {meas}). Ensure a `hole` feature "
                f"with op='cut' passes fully through the parent along its axis with "
                f"the declared diameter. Do not change other features.")
    if claim == "uniform_thickness_mm":
        return (f"`{node}` thickness is {meas} but must be {exp}. Set the pattern's "
                f"per-instance thickness param (the smallest dimension of "
                f"`{node}.params.feature.params`) to {exp}. Do NOT change "
                f"`{node}.params.count`.")
    if claim == "taper":
        return (f"`{node}` taper direction is wrong (got {meas}, need {exp}). Swap "
                f"the base/top radii (or protrusion) so it tapers '{exp}'. Change "
                f"only this feature.")
    if claim == "no_interference":
        return (f"Components `{node}` overlap by {meas} mm³ — distinct bodies must NOT "
                f"intersect. Shrink the mating component's footprint, or change the "
                f"mate/offset so they meet at a face instead of colliding (declare an "
                f"interference fit only if intended).")
    if claim == "contact":
        return (f"Components `{node}` are not touching (gap {meas}). Fix the mate or the "
                f"component sizes so `{node}` actually mate — no floating parts.")
    if claim == "concentric_alignment":
        return (f"`{node}` axes are off by {meas}. Use a `concentric` mate (or correct the "
                f"placement) so the two are coaxial.")
    if claim == "fit":
        return (f"`{node}` fit is wrong (clearance {meas}). Adjust bore/shaft diameters so "
                f"the declared fit holds.")
    if claim.startswith("envelope_"):
        dim = "diameter" if claim == "envelope_diameter_mm" else claim.split("_")[1].upper()
        return (f"Overall {dim} mismatch: built {meas}, declared {exp}. These are "
                f"inconsistent — fix EITHER side so they agree AND match the original "
                f"prompt:\n"
                f"  (a) if the part should be {exp}: grow the driving feature (e.g. "
                f"radial reach of the pattern / a feature's size) to reach {exp}; or\n"
                f"  (b) if {meas} is actually correct for the prompt: set the declared "
                f"`envelope` to the TRUE overall size (~{meas}) with a sensible tolerance.\n"
                f"Do not change unrelated declared asserts.")
    return f"Fix `{node}.{claim}`: measured {meas}, expected {exp}."


def _decide(l2: dict, vision: dict | None, meshlib: dict | None) -> dict:
    """Deterministic verdict from the verification layers."""
    # HALT: L2 could not run / mesh load failure (uninterpretable).
    if l2 is None or "checks" not in l2:
        return {"decision": "HALT",
                "reasoning": "Solid inspection (L2) did not produce results; cannot verify intent.",
                "discrepancies_found": [], "recommendations_for_planner": None,
                "confidence": "LOW"}

    failed = [c for c in l2["checks"] if not c["passed"]]
    if failed:
        failed.sort(key=lambda c: _PRIORITY.index(c["claim"]) if c["claim"] in _PRIORITY else 99)
        blocking = failed[0]
        # ALL failing checks are surfaced (most-blocking first). When several
        # checks fail there is nothing passing to protect, so giving the planner
        # the complete, node-keyed fix list converges far faster than one-at-a-time
        # (which previously left the planner unaware of e.g. a 45mm-thick blade).
        recs = [_repair_instruction(c) for c in failed]
        recommendation = ("Fix ALL of the following (most-blocking first); re-emit the full IR:\n"
                          + "\n".join(f"{i+1}. {r}" for i, r in enumerate(recs)))
        reasoning = (f"L2 deterministic ground truth failed {len(failed)} check(s). "
                     f"Most-blocking: {blocking['node']}.{blocking['claim']} — "
                     f"measured {blocking['measured']}, expected {blocking['expected']}.")
        return {"decision": "REDESIGN", "reasoning": reasoning,
                "discrepancies_found": _discrepancies(l2, vision),
                "recommendations_for_planner": recommendation,
                "confidence": "HIGH"}

    # L2 all-pass. Vision (L3) is advisory only — note disagreement, do not block.
    disc = _discrepancies(l2, vision)
    note = (" Vision flagged possible issues but L2 (ground truth) passed all "
            "declared claims; approving." if disc else "")
    return {"decision": "APPROVED",
            "reasoning": "All deterministic L2 checks against declared IR claims passed." + note,
            "discrepancies_found": disc, "recommendations_for_planner": None,
            "confidence": "HIGH"}


def _discrepancies(l2: dict, vision: dict | None) -> list[str]:
    if not vision:
        return []
    out = []
    for d in vision.get("suspected_defects", []) or []:
        out.append(f"vision suspected '{d}' (advisory; L2 is authoritative)")
    return out


INSTRUCTION = """You are a senior CAD QA reviewer. You will be given a verdict
already decided by deterministic geometry checks (the ground truth) plus the
design intent and any advisory vision findings. Write a concise, professional
one-paragraph rationale for the verdict for a human engineer. Do not change the
verdict. Output ONLY JSON: {"narration": "..."}"""

root_agent = Agent(
    name="adversarial_reviewer",
    model=get_model_name("reviewer"),
    description="Narrates deterministic-first CAD review verdicts (L2 ground truth over advisory vision).",
    instruction=INSTRUCTION,
    tools=[],
)


def run_review(design_intent: dict, l2_results: dict,
               vision_findings: dict | None = None,
               meshlib_findings: dict | None = None,
               narrate: bool = False) -> dict:
    """Cross-reference verification layers and return a routing verdict.

    Args:
        design_intent: compact IR (features + envelope) — intent, not kernel data.
        l2_results: output of solid_inspector.inspect_solid (node-keyed checks).
        vision_findings: optional L3 advisory findings.
        meshlib_findings: optional L4 (only meaningful for custom/mesh_only).
        narrate: if True, ask the LLM for a human-readable rationale (best-effort).

    Returns:
        {decision, reasoning, discrepancies_found, recommendations_for_planner, confidence}
    """
    verdict = _decide(l2_results, vision_findings, meshlib_findings)
    if narrate:
        verdict["reasoning"] = _narrate(design_intent, verdict) or verdict["reasoning"]
    return verdict


def _narrate(design_intent: dict, verdict: dict) -> str | None:
    msg = (f"Design intent:\n{json.dumps(design_intent, indent=2)}\n\n"
           f"Decided verdict:\n{json.dumps(verdict, indent=2)}\n\n"
           f"Write the one-paragraph rationale JSON.")
    session_id = str(uuid.uuid4())
    ss = InMemorySessionService()

    async def _mk():
        await ss.create_session(app_name="reviewer_agent", user_id="user", session_id=session_id)
    try:
        asyncio.run(_mk())
        runner = Runner(agent=root_agent, app_name="reviewer_agent", session_service=ss)
        content = types.Content(role="user", parts=[types.Part(text=msg)])
        events = list(runner.run(user_id="user", session_id=session_id, new_message=content))
        for ev in events:
            if ev.is_final_response() and ev.content and ev.content.parts:
                parsed = safe_parse_json(ev.content.parts[0].text)
                if parsed and parsed.get("narration"):
                    return parsed["narration"]
    except Exception as e:
        logging.getLogger("google_adk").warning(f"Reviewer narration unavailable: {e}")
    return None


# ── Backward-compatible shim for the legacy mesh-based pipeline path ──────────
def run_adversarial_review(design_brief: dict, static_results: dict,
                           ai_findings: dict) -> dict:
    """Legacy entry (mesh static + AI findings). Retained so older callers work;
    the IR pipeline uses `run_review`."""
    l2 = {"checks": [{"node": "mesh", "claim": "static",
                      "passed": not static_results.get("hard_failures"),
                      "measured": static_results.get("hard_failures", []),
                      "expected": []}]}
    return _decide(l2, ai_findings, None)
