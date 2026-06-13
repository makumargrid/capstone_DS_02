"""
core/intent_resolver.py — Intent Resolution stage (before planning).

Unifies clarification, standards grounding, and Spec confirmation into a single
gate before the planner runs. After this stage, the Spec is frozen and consumed
by both planner and checker as the single source of truth.

FLOW:
  1. Draft Spec (reuse extract_spec)
  2. Ground dimensions from standards (Prompt 8)
  3. Detect adaptivity (engineer vs general user)
  4. Pin explicit numbers from prompt
  5. Human confirmation gate (interactive) or auto-confirm (non-interactive)

CALLED BY: pipeline.py (before planner)
"""
from __future__ import annotations
import re
import json
import logging

logger = logging.getLogger("pipeline")


def _is_engineer(prompt: str) -> bool:
    """Detect if the user writes like an engineer (technical language)."""
    technical = [
        "diameter", "radius", "tolerance", "bore", "frustum", "taper",
        "extrude", "fillet", "chamfer", "counterbore", "thread", "pitch",
        "mm", "cm", "tolerance", "spec", "iso", "ansi", "fits",
        "h7", "h6", "clearance", "interference", "fit",
    ]
    count = sum(1 for t in technical if t in prompt.lower())
    return count >= 3


def _pin_dimensions(prompt: str) -> list[dict]:
    """Extract explicitly stated numeric dimensions from the prompt.
    Returns list of {param, value, target, raw_text}."""
    pinned = []
    # Pattern: "100mm base diameter", "60mm height", "2mm thick", "M6 bolt"
    patterns = [
        (r'(\d+(?:\.\d+)?)\s*mm\s*(?:base|hub)?\s*diameter', 'base_diameter_mm', 'hub'),
        (r'(\d+(?:\.\d+)?)\s*mm\s*(?:top)?\s*diameter', 'top_diameter_mm', 'hub'),
        (r'(\d+(?:\.\d+)?)\s*mm\s*height', 'height_mm', 'hub'),
        (r'(\d+(?:\.\d+)?)\s*mm\s*thick', 'uniform_thickness_mm', 'body'),
        (r'(\d+(?:\.\d+)?)\s*mm\s*(?:through)?\s*bore', 'bore_diameter_mm', 'bore'),
        (r'(\d+)\s*(?:teeth|fins?|holes?|bolts?|slots?)', 'count', 'features'),
    ]
    for pat, param, target in patterns:
        for m in re.finditer(pat, prompt.lower()):
            pinned.append({
                "param": param, "value": float(m.group(1)) if '.' in m.group(1) or m.group(1).isdigit() else int(m.group(1)),
                "target": target, "raw": m.group(0),
            })
    return pinned


def _ground_spec(spec: list[dict], prompt: str) -> list[dict]:
    """Ground spec requirements with standards values where dimensions are missing.
    Returns updated spec with source citations.

    Priority order:
      1. Bolt clearance hole (for bore/hole targets mentioning M-size bolt)
      2. General standards lookup (bolt dimensions, fits, materials)
    """
    from core.standards import lookup_standard, lookup_clearance_hole

    for r in spec:
        if r.get("expected") is not None:
            continue  # Already has a value

        desc = r.get("description", "")
        target = r.get("target", "")

        # Priority 1: bolt clearance hole for bore/hole targets
        # When a bore/hole mentions an M-bolt size, use the clearance hole
        # diameter (ISO 273), NOT the bolt major diameter.
        if target.lower() in ("bore", "hole"):
            m = re.search(r'M(\d+)', (desc + " " + prompt).upper())
            if m:
                bolt = m.group(0)
                hole = lookup_clearance_hole(bolt)
                if hole:
                    r["expected"] = hole["value"]
                    r["source"] = hole["source"]
                    r["tolerance"] = r.get("tolerance") or 0.5
                    continue  # Don't overwrite with general lookup

        # Priority 2: general standards lookup from description or target+prompt context
        query = f"{target} {desc} {prompt[:200]}"
        std = lookup_standard(query)

        if std:
            r["expected"] = std.get("value")
            r["source"] = std.get("source", "engineering standard")
            r["tolerance"] = r.get("tolerance") or 0.5

    return spec


def _generate_adaptive_questions(prompt: str, spec: list[dict], pinned: list[dict],
                                  is_engineer: bool, profile: dict) -> str:
    """Generate a batched set of substantive, decision-relevant questions.

    Rules (from skills/intent_resolution/SKILL.md):
    - Only ask about information that actually changes the design.
    - Prefer standards-grounded defaults with source citations.
    - Batch related questions; return empty string if nothing substantive is missing.
    - Adapt tone: engineers get precise numeric questions; general users get plain-language.
    """
    questions: list[str] = []
    specified_targets = {r.get("target", "") for r in spec}
    specified_params = {r.get("param", "") for r in spec}

    # Determine what's already covered
    has_dimensions = any(r.get("expected") is not None and r.get("claim") == "dimension" for r in spec)
    has_bolt_holes = "holes" in specified_targets or "hole" in specified_targets
    has_material = any(w in prompt.lower() for w in ("aluminum", "steel", "abs", "pla", "nylon", "petg", "titanium", "stainless"))
    has_process = any(w in prompt.lower() for w in ("fdm", "sla", "cnc", "milled", "printed", "cast", "machined"))
    has_load = any(w in prompt.lower() for w in ("kg", "lbs", "load", "weight", "heavy", "light"))
    has_mounting = any(w in prompt.lower() for w in ("mount", "bolt", "screw", "wall", "stud", "frame", "attach"))

    # Count how many numeric dimensions are explicitly specified
    num_pinned = len(pinned)

    low_detail = num_pinned < 2 and not has_dimensions and not has_load and not has_mounting

    if is_engineer:
        # ── Engineer path: precise dimensional/process questions ──
        if not has_material and not has_process:
            questions.append(
                "Material & process: ABS (FDM), aluminum (CNC), or another? "
                "This determines min wall thickness, tolerances, and DFM rules."
            )
        elif not has_material:
            questions.append(
                "Which material? (e.g., ABS, aluminum, steel — affects min wall thickness and tolerances)"
            )
        elif not has_process:
            questions.append(
                "Which manufacturing process? (FDM, SLA, CNC, etc. — affects DFM thresholds)"
            )

        if has_bolt_holes:
            # Check if M-size is specified; if not, ask
            from core.standards import lookup_clearance_hole
            m_match = None
            import re as _re
            for r in spec:
                desc = (r.get("description", "") + " " + prompt).upper()
                mm = _re.search(r'M(\d+)', desc)
                if mm:
                    m_match = mm.group(0)
                    break
            if not m_match:
                # Propose a default bolt size with clearance hole
                default_bolt = "M6"
                hole = lookup_clearance_hole(default_bolt)
                if hole:
                    questions.append(
                        f"What bolt size for the mounting holes? "
                        f"(Default: {default_bolt} → Ø{hole['value']}mm clearance per {hole['source']}. "
                        f"Specify a different size if needed.)"
                    )
                else:
                    questions.append(
                        "What bolt size for the mounting holes? (e.g., M6, M8, M10)"
                    )

        if not has_load and low_detail:
            questions.append(
                "Approximate load this part will carry? "
                "(e.g., <1 kg decorative, 5–10 kg functional, 50+ kg structural — "
                "drives wall thickness and ribbing)"
            )

        if not has_mounting and low_detail:
            questions.append(
                "How will this part mount? (e.g., bolted to a wall, clamped to a pipe, "
                "pressed into a bearing — determines feature placement and hole patterns)"
            )

    else:
        # ── General-user path: plain-language, use-case questions ──
        part_name = ""
        for r in spec:
            t = r.get("target", "")
            if t in ("bracket", "housing", "enclosure", "mount", "flange", "body", "hub", "gear"):
                part_name = t
                break
        if not part_name:
            # Extract from prompt
            words = prompt.lower().split()
            for w in ("bracket", "housing", "enclosure", "mount", "flange", "adapter", "holder", "stand"):
                if w in words:
                    part_name = w
                    break
        if not part_name:
            part_name = "part"

        if not has_mounting and not has_bolt_holes:
            questions.append(
                f"What will this {part_name} attach to? "
                f"(e.g., a wall, another part, a pipe — this helps determine how it mounts)"
            )

        if not has_load and low_detail:
            questions.append(
                f"What will this {part_name} support or carry? "
                f"(e.g., a small shelf, a camera, heavy machinery — this determines how sturdy it needs to be)"
            )

        if not has_material and not has_process:
            # For general users, propose ABS/FDM as common default
            questions.append(
                f"Material preference? "
                f"(Default: standard 3D-printed plastic (ABS/PLA) is fine for most uses. "
                f"Choose metal if it needs to hold significant weight or handle heat.)"
            )

        # Fill missing dimensions from standards where possible, confirm visually
        if low_detail and has_bolt_holes:
            from core.standards import lookup_clearance_hole
            import re as _re
            m_match = None
            for r in spec:
                desc = (r.get("description", "") + " " + prompt).upper()
                mm = _re.search(r'M(\d+)', desc)
                if mm:
                    m_match = mm.group(0)
                    break
            if not m_match:
                default_bolt = "M6"
                hole = lookup_clearance_hole(default_bolt)
                if hole:
                    questions.append(
                        f"Based on standard practice, mounting holes will be sized for "
                        f"{default_bolt} bolts (Ø{hole['value']}mm clearance per {hole['source']}). "
                        f"Does that work for your use, or do you need a different size?"
                    )

        # Wall thickness default for low-detail general prompts
        if low_detail and not any(r.get("claim") == "uniform_thickness_mm" for r in spec):
            min_wall = profile.get("min_wall_mm", 2.0)
            questions.append(
                f"Wall thickness will be at least {min_wall}mm "
                f"(standard minimum for {profile.get('process_key', 'FDM').upper()}). "
                f"This will be confirmed visually — no numbers needed from you."
            )

    if not questions:
        return ""

    # Batch into a single message
    if is_engineer:
        header = "## Design Clarifications\n\nA few specifics to nail down before we freeze the spec:\n\n"
    else:
        header = "## A Few Questions to Get Your Design Right\n\n"

    return header + "\n\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))


def resolve_intent(prompt: str, profile: dict, interactive: bool = False,
                   question_handler=None) -> dict:
    """Run the Intent Resolution stage.

    Returns:
        {spec, confirmed, clarification_notes, is_engineer, pinned_dimensions}
    """
    from core.spec import extract_spec

    # 1. Draft the Spec
    spec = extract_spec(prompt)

    # 2. Ground with standards
    spec = _ground_spec(spec, prompt)

    # 3. Pin explicit dimensions
    pinned = _pin_dimensions(prompt)

    # 4. Detect adaptivity
    is_eng = _is_engineer(prompt)

    # 5. Adaptive questioning: ask only what's decision-relevant and still missing
    clarification_notes = []

    if interactive and question_handler:
        adaptive_qs = _generate_adaptive_questions(prompt, spec, pinned, is_eng, profile)
        if adaptive_qs:
            response = question_handler(adaptive_qs)
            if response and response.strip():
                clarification_notes.append(response)

        # 6. Confirmation gate: show frozen spec, get approval
        summary = _format_spec_summary(spec, pinned, is_eng)
        summary += "\n\nDo you confirm this specification? (yes/edit/no)"
        response = question_handler(summary)

        if response and response.lower().startswith(("yes", "y", "confirm", "ok")):
            confirmed = True
        elif response and "no browser answer arrived in time" in response.lower():
            confirmed = True
            if response and response.strip():
                clarification_notes.append(response)
        elif response and response.lower().startswith(("no", "n", "cancel")):
            confirmed = False
        else:
            # Treat any other response as edit notes
            confirmed = True
            if response and response.strip():
                clarification_notes.append(response)
    else:
        confirmed = True  # Auto-confirm in non-interactive mode

    return {
        "spec": spec,
        "confirmed": confirmed,
        "clarification_notes": clarification_notes,
        "is_engineer": is_eng,
        "pinned_dimensions": pinned,
    }


def _format_spec_summary(spec: list[dict], pinned: list[dict], is_engineer: bool) -> str:
    """Format the Spec for human confirmation."""
    lines = ["## Draft Specification", ""]
    lines.append("Your part will have the following requirements:")

    for r in spec:
        claim = r.get("claim", "?")
        target = r.get("target", "?")
        expected = r.get("expected")
        source = r.get("source", "")
        desc = r.get("description", "")

        if expected is not None:
            if claim == "count":
                lines.append(f"- {expected} {target}")
            elif claim == "dimension":
                lines.append(f"- {target} {r.get('param','')} = {expected}mm")
            elif claim == "bore_diameter_mm":
                lines.append(f"- {target} diameter = {expected}mm")
            elif claim == "uniform_thickness_mm":
                lines.append(f"- {target} thickness = {expected}mm")
            elif claim == "taper":
                lines.append(f"- {target} taper: {expected}")
            else:
                lines.append(f"- {target}: {expected} ({claim})")
        else:
            lines.append(f"- {target}: {desc or 'present'} ({claim})")

        if source:
            lines[-1] += f"  [↗ {source}]"

    if pinned:
        lines.append("")
        lines.append("### Explicitly stated dimensions:")
        for p in pinned:
            lines.append(f"  - {p['raw']}")

    if is_engineer:
        lines.append("")
        lines.append("(Technical/engineering terminology detected — using concise format)")

    return "\n".join(lines)


def explain_plan(ir: dict) -> str:
    """Generate a plain-language explanation from an IR design."""
    features = ir.get("features", [])
    process = ir.get("process", "FDM")
    env = ir.get("envelope", {})

    lines = [
        f"A {process} part, roughly {env.get('x_mm', '?')}×{env.get('y_mm', '?')}×{env.get('z_mm','?')}mm.",
        "",
        "Feature tree:",
    ]

    for f in features:
        ftype = f.get("type", "?")
        fid = f.get("id", "?")
        op = f.get("op", "union")
        params = f.get("params", {})
        asserts = f.get("asserts", {})

        if ftype == "circular_pattern":
            count = params.get("count", "?")
            sub = params.get("feature", {})
            stype = sub.get("type", "?")
            lines.append(f"- '{fid}': {count}× {stype} arranged in a circle ({op})")
        elif ftype == "cylinder":
            r, h = params.get("radius", "?"), params.get("height", "?")
            lines.append(f"- '{fid}': cylinder (radius {r}mm, height {h}mm) [{op}]")
        elif ftype == "cone":
            rb, rt, h = params.get("r_base", "?"), params.get("r_top", "?"), params.get("height", "?")
            lines.append(f"- '{fid}': tapered cone (base {rb}mm→top {rt}mm, height {h}mm) [{op}]")
        elif ftype == "box":
            l, w, h = params.get("length", "?"), params.get("width", "?"), params.get("height", "?")
            lines.append(f"- '{fid}': box ({l}×{w}×{h}mm) [{op}]")
        elif ftype == "hole":
            d = params.get("diameter", "?")
            lines.append(f"- '{fid}': hole (Ø{d}mm) [{op}]")
        elif ftype == "fillet":
            r = params.get("radius", "?")
            lines.append(f"- '{fid}': fillet (R{r}mm) [{op}]")
        elif ftype == "chamfer":
            cl = params.get("length", "?")
            lines.append(f"- '{fid}': chamfer (length {cl}mm) [{op}]")
        elif ftype == "profile":
            op_type = params.get("operation", "extrude")
            depth = params.get("depth", "?")
            lines.append(f"- '{fid}': profile ({op_type} {depth}mm) [{op}]")
        else:
            lines.append(f"- '{fid}': {ftype} [{op}] (params: {params})")

        if asserts:
            lines.append(f"  asserts: {asserts}")

    return "\n".join(lines)