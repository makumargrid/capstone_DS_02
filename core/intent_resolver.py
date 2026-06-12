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
        (r'(\d+)\s*(?:blades?|teeth|fins?|holes?|bolts?|slots?)', 'count', 'features'),
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
    Returns updated spec with source citations."""
    from core.standards import lookup_standard

    for r in spec:
        if r.get("expected") is not None:
            continue  # Already has a value

        desc = r.get("description", "")
        target = r.get("target", "")

        # Try standards lookup from description or target+prompt context
        query = f"{target} {desc} {prompt[:200]}"
        std = lookup_standard(query)

        if std:
            r["expected"] = std.get("value")
            r["source"] = std.get("source", "engineering standard")
            r["tolerance"] = r.get("tolerance") or 0.5

        # If it's a bore and no standard found, try bolt clearance
        if r.get("expected") is None and target.lower() in ("bore", "hole"):
            # Check for M-size bolt references
            m = re.search(r'M(\d+)', prompt.upper())
            if m:
                bolt = m.group(0)
                from core.standards import lookup_clearance_hole
                hole = lookup_clearance_hole(bolt)
                if hole:
                    r["expected"] = hole["value"]
                    r["source"] = hole["source"]

    return spec


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

    # 5. Confirmation gate
    clarification_notes = []

    reference_image = None
    if interactive and question_handler:
        # Check for reference image in the session
        try:
            from interaction.image_intake import get_reference_image
            # Session dir may not be known at this level — skip if not available
        except ImportError:
            pass

        summary = _format_spec_summary(spec, pinned, is_eng)
        if reference_image:
            summary = "🖼️ Reference image is loaded for shape comparison.\n\n" + summary
        summary += "\n\nDo you confirm this specification? (yes/edit/no)"
        response = question_handler(summary)

        if response and response.lower().startswith(("yes", "y", "confirm", "ok")):
            confirmed = True
        elif response and response.lower().startswith(("no", "n", "cancel")):
            confirmed = False
        else:
            # Treat any other response as edit notes
            confirmed = True
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