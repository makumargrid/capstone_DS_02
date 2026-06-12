"""
core/spec.py — the independent intent contract (Phase 1).

WHY: the planner used to write its OWN acceptance asserts, so it could converge
     by declaring a trivial bar (e.g. a "centrifugal impeller" became 7 flat
     plates because the only blade claim was count=7). The Spec fixes that: it
     is extracted from the prompt INDEPENDENTLY of the planner, frozen, and used
     as the acceptance contract. The planner must COVER it; it cannot weaken it.

WHAT:
  Requirement   one checkable intent item {id, description, claim, target,
                expected, param, tolerance, severity}.
  extract_spec(prompt) -> [Requirement]  (LLM via core.llm_client + deterministic
                domain augmentation; falls back to a regex/keyword spec offline).
  check_coverage(spec, l2_checks, design) -> {covered, missing[], report[]}
                deterministic: each REQUIRED requirement must be satisfied by a
                passing L2 check (count/taper/bore/thickness) OR by IR structure
                (feature_present, swept-blade, named dimension param).

CALLED BY: pipeline.py (extract once up front; coverage-gate before APPROVED).
CALLS: core/llm_client.call_llm, core/model_config.get_model_name.
"""
from __future__ import annotations
import re
import json

# claim vocabulary the Spec speaks (superset of L2 claims + structural/qualitative)
_CLAIMS = {"feature_present", "count", "swept", "taper", "bore_diameter_mm",
           "uniform_thickness_mm", "dimension"}

# Domains whose bladed/vaned features are aerodynamically SWEPT/CURVED, not flat.
_SWEPT_DOMAINS = ("impeller", "turbine", "compressor", "propeller", "fan",
                  "rotor", "pump", "screw", "auger", "turbofan")
_BLADE_WORDS = ("blade", "vane", "fin", "flute", "wing")

_EXTRACT_INSTRUCTION = """You extract a FIXED acceptance SPEC from a CAD request.
You are NOT the designer — you only list what the finished part MUST satisfy, so a
separate checker can verify it. Be faithful to the user's intent and to obvious
domain meaning (a "centrifugal impeller" has CURVED/SWEPT aerodynamic blades, not
flat plates; a "gear" has teeth; an "enclosure" is hollow).

Output ONLY JSON: {"requirements": [ ... ]}. Each requirement:
  {"id","description","claim","target","expected","param","tolerance","severity"}
  claim ∈ feature_present | count | swept | taper | bore_diameter_mm |
          uniform_thickness_mm | dimension
  target = the feature/role name (e.g. "hub","blades","bore","body","teeth").
  expected = number/bool/string or null; param (for dimension) e.g.
             "base_diameter_mm"/"top_diameter_mm"/"height_mm"; tolerance = mm or null;
  severity = "required" (must hold) or "preferred".

CRITICAL CONSTRAINTS (violations make requirements impossible to verify):
1. `feature_present` targets MUST be a SINGLE LOWERCASE WORD that names a concrete
   geometry feature (hub, bore, blades, teeth, holes, fins, walls, body, shaft, gear,
   housing, bracket, enclosure, lid). Do NOT use compound names, abstract concepts, or
   domain jargon like "centrifugal_impeller_form", "smooth_surfaces", "aerodynamic_form",
   "performance_surfaces". If you cannot name it with a single concrete word, skip it.
2. `dimension` claims MUST only capture dimensions EXPLICITLY stated as numbers in the
   prompt. Do NOT infer or calculate derived values (e.g., do not compute tip_diameter
   from hub radius). If the value is not literally stated, use `"expected": null` — or
   skip the requirement entirely if it adds no checkable constraint.
3. Keep ids short (r1, r2, ...). Keep the total count to what is verifiable.
4. For taper: use `"expected": "outward_base"` when hub is wider at the bottom, or
   `"expected": "outward_top"` when wider at top. Do NOT use `true` or `false`."""


def _augment_domain(prompt: str, reqs: list[dict]) -> list[dict]:
    """Deterministic domain knowledge: bladed rotating machines need SWEPT blades.
    Ensures the laziest 'flat plate' interpretation cannot satisfy the spec."""
    pl = prompt.lower()
    if any(d in pl for d in _SWEPT_DOMAINS) and any(b in pl for b in _BLADE_WORDS):
        target = next((r.get("target") for r in reqs
                       if r.get("claim") == "count" and r.get("target")), "blades")
        if not any(r.get("claim") == "swept" for r in reqs):
            reqs.append({"id": f"r{len(reqs)+1}", "claim": "swept", "target": target,
                         "expected": True, "param": None, "tolerance": None,
                         "severity": "required",
                         "description": f"{target} must be swept/curved (aerodynamic), not flat"})
        # PROTRUSION: rotating bladed parts must have features that visibly protrude
        if not any(r.get("claim") == "protrusion" and r.get("target") == target for r in reqs):
            reqs.append({"id": f"r{len(reqs)+1}", "claim": "protrusion", "target": target,
                         "expected": True, "param": None, "tolerance": None,
                         "severity": "required",
                         "description": f"{target} must visibly protrude beyond the hub surface"})
        # CONTACT: features must maintain contact with parent across full height
        if not any(r.get("claim") == "contact" and r.get("target") == target for r in reqs):
            reqs.append({"id": f"r{len(reqs)+1}", "claim": "contact", "target": target,
                         "expected": True, "param": None, "tolerance": None,
                         "severity": "required",
                         "description": f"{target} must maintain contact with hub surface across full height"})
    return reqs


def _fallback_spec(prompt: str) -> list[dict]:
    """Offline spec: counts, dimensions, bores, taper, and swept via regex/keywords.
    Used when the LLM-based extract_spec is unavailable. Covers enough to make the
    coverage gate meaningful even during a Gemini outage."""
    reqs: list[dict] = []

    # --- Count patterns: "7 blades", "4 bolt holes", "20 teeth" ---
    for m in re.finditer(r"(\d+)\s+(?:[a-z]+\s+)?([a-z]+?)s?\b", prompt.lower()):
        n, word = int(m.group(1)), m.group(2)
        if word.rstrip("s") in [w for w in _BLADE_WORDS] + list(_CONCRETE_TARGETS):
            reqs.append({"id": f"r{len(reqs)+1}", "claim": "count", "target": word,
                          "expected": n, "param": None, "tolerance": None,
                          "severity": "required", "description": f"{n} {word}"})

    # --- Dimension patterns: "100mm base diameter", "60mm height", "15mm bore" ---
    _DIM_PATTERNS = [
        (r"(\d+)\s*mm\s*(?:base|hub)?\s*diameter", "base_diameter_mm", "hub"),
        (r"(\d+)\s*mm\s*(?:top)?\s*diameter", "top_diameter_mm", "hub"),
        (r"(\d+)\s*mm\s*height", "height_mm", "hub"),
        (r"(\d+)\s*mm\s*thick", "uniform_thickness_mm", "body"),
    ]
    for pattern, param, target in _DIM_PATTERNS:
        for m in re.finditer(pattern, prompt.lower()):
            reqs.append({"id": f"r{len(reqs)+1}", "claim": "dimension", "target": target,
                          "expected": float(m.group(1)), "param": param,
                          "tolerance": 3.0, "severity": "required",
                          "description": f"{target} {param.replace('_',' ')} {m.group(1)}mm"})

    # --- Bore patterns: "15mm through bore", "bore of 15mm" ---
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*mm\s*(?:through)?\s*bore", prompt.lower()):
        reqs.append({"id": f"r{len(reqs)+1}", "claim": "bore_diameter_mm", "target": "bore",
                      "expected": float(m.group(1)), "param": None, "tolerance": 1.0,
                      "severity": "required",
                      "description": f"bore diameter {m.group(1)}mm"})

    # --- Taper patterns: "tapered", "wider at the base", "outward taper" ---
    if re.search(r"taper(?:ed|s)?|wider\s+(?:at\s+)?(?:the\s+)?base", prompt.lower()):
        reqs.append({"id": f"r{len(reqs)+1}", "claim": "taper", "target": "hub",
                      "expected": "outward_base", "param": None, "tolerance": None,
                      "severity": "required", "description": "hub tapers outward at base"})

    # --- Swept: keyword presence (also handled by _augment_domain) ---
    if not any(r.get("claim") == "swept" for r in reqs):
        if re.search(r"swept|curved|twist(?:ed)?", prompt.lower()):
            reqs.append({"id": f"r{len(reqs)+1}", "claim": "swept", "target": "blades",
                          "expected": True, "param": None, "tolerance": None,
                          "severity": "required", "description": "blades must be swept/curved"})

    return _augment_domain(prompt, reqs)


# Concrete feature names the check_coverage engine can actually resolve.
_CONCRETE_TARGETS = frozenset({
    "hub", "bore", "blades", "blade", "body", "teeth", "tooth", "holes", "hole",
    "fins", "fin", "walls", "wall", "shaft", "gear", "housing", "bracket",
    "enclosure", "lid", "base", "top", "boss", "pocket", "flange", "ribs", "rib",
    "slots", "slot", "pins", "pin", "threads", "thread", "chamfer", "fillet",
})


def _is_verifiable_target(target: str) -> bool:
    """Return True if `target` is a single concrete word the coverage engine can match."""
    if not target:
        return False
    # Multi-word targets (contain space or underscore-compound) are abstract
    if " " in target or "_" in target:
        return False
    return True  # single-word targets are allowed even if not in the hardcoded set


def extract_spec(prompt: str) -> list[dict]:
    """Extract the immutable intent Spec from the prompt (independent of planner)."""
    try:
        from .llm_client import call_llm
        from .model_config import get_model_name
        raw = call_llm(get_model_name("intent"), f"Request:\n{prompt}", _EXTRACT_INSTRUCTION)
        data = json.loads(re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
                          [re.sub(r"```(?:json)?", "", raw).replace("```", "").strip().find("{"):])
        reqs = data.get("requirements", [])
        for i, r in enumerate(reqs):           # normalize
            r.setdefault("id", f"r{i+1}")
            r.setdefault("severity", "required")
            for k in ("expected", "param", "tolerance", "target", "description"):
                r.setdefault(k, None)
        reqs = [r for r in reqs if r.get("claim") in _CLAIMS]

        # Post-processing: drop requirements that are structurally unverifiable.
        # These phantom requirements doom every run — no IR can ever satisfy them.
        filtered = []
        for r in reqs:
            claim, target, expected = r.get("claim"), r.get("target"), r.get("expected")
            # Drop feature_present with abstract/multi-word targets
            if claim == "feature_present" and not _is_verifiable_target(target):
                continue
            # Drop dimension requirements with null expected (no number to check against)
            if claim == "dimension" and expected is None:
                continue
            filtered.append(r)
        reqs = filtered
    except Exception:
        reqs = _fallback_spec(prompt)
    return _augment_domain(prompt, reqs)


# ── Coverage (deterministic) ────────────────────────────────────────────────
def _features(design) -> dict:
    """role/id -> feature dict (incl. a pattern's nested feature under its own id)."""
    feats = design["features"] if isinstance(design, dict) else [f.model_dump() for f in design.features]
    out = {}
    for f in feats:
        out[f["id"]] = f
        sub = (f.get("params") or {}).get("feature")
        if isinstance(sub, dict):
            out.setdefault(f["id"] + ":item", sub)
    return out


def _match(target: str, feats: dict):
    if target in feats:
        return feats[target]
    for k, v in feats.items():
        if target and (target in k or k in target):
            return v
    return None


def _dim_from_params(feat: dict, param: str):
    p = feat.get("params", {})
    if param == "base_diameter_mm" and "r_base" in p: return p["r_base"] * 2
    if param == "top_diameter_mm" and "r_top" in p: return p["r_top"] * 2
    if param == "height_mm": return p.get("height")
    if param == "diameter_mm": return p.get("diameter") or (p.get("radius", 0) * 2)
    return p.get(param.replace("_mm", ""))


def check_coverage(spec: list[dict], l2_checks: list[dict], design) -> dict:
    """Every REQUIRED requirement must be satisfied by a passing L2 check or IR
    structure. Returns {covered, missing:[{id,description,why}], report:[...]}."""
    feats = _features(design)
    passed = {(c["node"], c["claim"]) for c in l2_checks if c["passed"]}
    missing, report = [], []

    for r in spec:
        if r.get("severity") != "required":
            continue
        claim, target = r.get("claim"), r.get("target")
        ok, why = False, ""

        if claim == "feature_present":
            ok = _match(target, feats) is not None
            why = "" if ok else f"no feature matching role '{target}'"
        elif claim == "protrusion":
            f = _match(target, feats)
            nodes = {target, (f or {}).get("id")}
            cand = [c for c in l2_checks if c.get("passed")
                    and c.get("claim") == "feature_contributes"
                    and c.get("node") in nodes]
            ok, why = bool(cand), ("" if cand else
                         f"no passing 'feature_contributes' check on '{target}' — "
                         f"feature is likely embedded inside its parent")
        elif claim == "contact":
            f = _match(target, feats)
            nodes = {target, (f or {}).get("id")}
            cand = [c for c in l2_checks if c.get("passed")
                    and c.get("claim") == "parent_contact"
                    and c.get("node") in nodes]
            ok, why = bool(cand), ("" if cand else
                         f"no passing 'parent_contact' check on '{target}' — "
                         f"feature may be detached from parent at some heights")
        elif claim == "swept":
            f = _match(target, feats)
            if f and f.get("type") in ("circular_pattern", "linear_pattern"):
                f = (f.get("params") or {}).get("feature")
            tw = (f or {}).get("params", {}).get("twist_deg", 0) if f else 0
            ok = bool(f) and f.get("type") == "blade" and (tw or 0) != 0
            why = "" if ok else f"'{target}' is not a swept blade (need type=blade, twist_deg≠0)"
        elif claim == "dimension":
            f = _match(target, feats)
            meas = _dim_from_params(f, r.get("param") or "") if f else None
            exp, tol = r.get("expected"), r.get("tolerance") or 2.0
            ok = meas is not None and exp is not None and abs(meas - exp) <= tol
            why = "" if ok else f"'{target}.{r.get('param')}'={meas} vs {exp}±{tol}"
        else:  # count / taper / bore_diameter_mm / uniform_thickness_mm
            l2claim = "bore_present" if claim == "bore_diameter_mm" else claim
            f = _match(target, feats)
            nodes = {target, (f or {}).get("id")}
            cand = [c for c in l2_checks if c.get("passed") and c.get("claim") == l2claim
                    and c.get("node") in nodes]
            if not cand:
                ok, why = False, f"no passing L2 '{l2claim}' check on '{target}'"
            elif claim in ("count", "uniform_thickness_mm") and r.get("expected") is not None:
                # the BUILT value (L2 measured) must match the SPEC's value — not the
                # planner's self-chosen assert. Closes the "assert a weaker number" loophole.
                meas = cand[0].get("measured")
                tol = r.get("tolerance") or (0 if claim == "count" else 0.5)
                try:
                    ok = abs(float(meas) - float(r["expected"])) <= tol
                except (TypeError, ValueError):
                    ok = False
                why = "" if ok else f"{claim} built={meas} but spec requires {r['expected']}"
            else:
                ok, why = True, ""

        report.append({"id": r["id"], "claim": claim, "target": target, "covered": ok})
        if not ok:
            missing.append({"id": r["id"], "description": r.get("description"), "why": why})

    return {"covered": not missing, "missing": missing, "report": report}


def coverage_feedback(missing: list[dict]) -> str:
    """Spec-targeted REDESIGN guidance for uncovered requirements."""
    lines = ["The design does NOT yet satisfy the user's intent SPEC. "
             "Address each uncovered requirement (do not weaken the spec):"]
    # Collect all failing dimension whys to detect r_base/r_top swap
    base_meas = top_meas = base_exp = top_exp = None
    for m in missing:
        why = m.get("why") or ""
        if "base_diameter_mm" in why:
            try:
                base_meas = float(why.split("=")[1].split(" ")[0])
                base_exp = float(why.split("vs ")[1].split("±")[0])
            except Exception:
                pass
        if "top_diameter_mm" in why:
            try:
                top_meas = float(why.split("=")[1].split(" ")[0])
                top_exp = float(why.split("vs ")[1].split("±")[0])
            except Exception:
                pass
    # Detect swap: measured base ≈ expected top AND measured top ≈ expected base
    swap_detected = (base_meas is not None and top_meas is not None
                     and base_exp is not None and top_exp is not None
                     and abs(base_meas - top_exp) < 3.0
                     and abs(top_meas - base_exp) < 3.0)

    for m in missing:
        why = m.get("why") or ""
        hint = ""
        if "swept blade" in why:
            hint = (" → use the `blade` primitive with twist_deg≠0 (NOT a flat `box`); "
                    "declare its `uniform_thickness_mm` and keep the pattern count.")
        elif swap_detected and ("base_diameter_mm" in why or "top_diameter_mm" in why):
            hint = (f" → r_base and r_top are SWAPPED. r_base is the radius at z=0 "
                    f"(the physical bottom of the part), r_top is at z=height (the top). "
                    f"For base_diam={base_exp:.0f}mm set r_base={base_exp/2:.0f}; "
                    f"for top_diam={top_exp:.0f}mm set r_top={top_exp/2:.0f}. "
                    f"Do NOT invert these. Also check that `taper` assert is "
                    f'"outward_base" (string), not true (boolean).')
        lines.append(f"- [{m['id']}] {m['description']}: {why}.{hint}")
    return "\n".join(lines)


# ── Decomposition judgment (Phase 2) ────────────────────────────────────────
# Decided INDEPENDENTLY of the planner (so it can't game it), and only where the
# object is genuinely an assembly of physically DISTINCT bodies.
_ASSEMBLY_HINTS = ("assembly", "unit with", "two pieces", "both pieces", "indoor",
                   "outdoor", "mounted on", "bolted to", "lid", "housing and",
                   "shaft and", "and a bracket", "multiple parts", "sub-assembly")

_DECOMPOSE_INSTRUCTION = """Decide whether a CAD request describes ONE monolithic
part or an ASSEMBLY of physically DISTINCT bodies that are made/joined separately.

Rule:
- ASSEMBLY only if there are ≥2 separate bodies that are distinct objects (different
  function/material, removable, or not one continuous solid) — e.g. an AC unit
  (indoor box + outdoor box + fan), an enclosure + lid, a shaft + housing.
- PART (monolithic) if the features share material / form ONE continuous solid —
  e.g. an impeller (hub+blades+bore are one piece), a bracket with holes, a gear.
Output ONLY JSON: {"mode":"part"|"assembly","components":[{"id","description"}],
"rationale":"..."}. For PART, components=[]. Use short role ids (e.g. indoor, fan)."""


def decompose(prompt: str) -> dict:
    """Judge part-vs-assembly and (if assembly) the component split.
    Returns {"mode","components":[{id,description}],"rationale"}. Conservative:
    falls back to PART unless ≥2 distinct components are clearly identified."""
    try:
        from .llm_client import call_llm
        from .model_config import get_model_name
        raw = call_llm(get_model_name("intent"), f"Request:\n{prompt}", _DECOMPOSE_INSTRUCTION)
        clean = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
        data = json.loads(clean[clean.find("{"):clean.rfind("}") + 1])
        comps = data.get("components") or []
        mode = "assembly" if (data.get("mode") == "assembly" and len(comps) >= 2) else "part"
        return {"mode": mode, "components": comps if mode == "assembly" else [],
                "rationale": data.get("rationale", "")}
    except Exception:
        pl = prompt.lower()
        if any(h in pl for h in _ASSEMBLY_HINTS):
            return {"mode": "part", "components": [],
                    "rationale": "assembly keyword seen, but no distinct components were identified"}
        return {"mode": "part", "components": [], "rationale": "default: monolithic part"}
