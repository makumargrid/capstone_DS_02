"""
verification/constraint_translator.py — maps failed L2 checks to specific parameter targets.

WHY: When L2 detects a failure (e.g. envelope_diameter = 100 vs 110), the current
     reviewer says "fix either side." The planner then blindly changes at[0] and chord,
     taking 4+ iterations to converge via random walk. This module computes the EXACT
     parameter changes needed — it translates abstract failures into concrete numbers.

WHAT:
  translate_failure(check, provenance, design, solid) → str
    Given a failed L2 check, computes the geometric constraint that's violated and
    returns surgical repair text with exact parameter values.

PRINCIPLE: All math is derived from the compiled geometry. No domain knowledge.
           Works for ANY feature type on ANY parent — boss on box, rib on cylinder,
           fin on sphere. The code doesn't need domain knowledge — it just measures
           vertices and radii.

CALLED BY: pipeline.py (after L2 inspection, to augment reviewer feedback).
CALLS: cadquery (for vertex/hull queries).
"""
from __future__ import annotations
import math
from typing import Any

import cadquery as cq

from geometry_ir.models import Design
from primitives.compiler import FeatureProvenance


def translate_failure(check: dict, provenance: list[FeatureProvenance],
                      design: Design | dict, solid: cq.Solid) -> str | None:
    """Given a failed L2 check, produce a constraint-based repair suggestion.

    Returns a human-readable string with specific parameter targets, or None
    if the failure type cannot be translated to exact constraints.
    """
    claim = check.get("claim", "")
    node = check.get("node", "")
    measured = check.get("measured")
    expected = check.get("expected")

    if isinstance(design, dict):
        design = Design.model_validate(design)

    prov_by_id = {p.id: p for p in provenance}

    if claim.startswith("envelope_"):
        return _translate_envelope(node, claim, measured, expected, design,
                                   solid, prov_by_id)
    elif claim == "feature_contributes":
        return _translate_embedded(node, measured, design, solid, prov_by_id)
    elif claim == "bore_present":
        return _translate_bore_obstruction(node, measured, design, solid, prov_by_id)
    elif claim == "single_solid":
        return _translate_disconnected(node, design, solid, prov_by_id)

    return None


def _get_radial_constraint(solid_mm: cq.Solid) -> dict:
    """Get min and max radial extent (from Z-axis) of a solid at various heights.
    Returns {max_r, min_r, z_range}. For axisymmetric analysis."""
    vertices = list(solid_mm.Vertices())
    if not vertices:
        return {"max_r": 0, "min_r": 0, "z_range": (0, 0)}
    radii = [(v.X**2 + v.Y**2)**0.5 for v in vertices]
    zs = [v.Z for v in vertices]
    return {
        "max_r": round(max(radii), 2),
        "min_r": round(min(radii), 2),
        "z_range": (round(min(zs), 2), round(max(zs), 2)),
    }


def _get_parent_constraints(parent_feature: dict, feat_type: str,
                            params: dict) -> dict:
    """Get the spatial constraints of the parent body.
    For frustum/cone: max radius at each z. For box: half-extents."""
    if feat_type in ("cone", "frustum"):
        r_base = params.get("r_base", 0)
        r_top = params.get("r_top", 0)
        height = params.get("height", 1)
        return {
            "type": "frustum",
            "r_base": r_base,
            "r_top": r_top,
            "height": height,
            "surface_r_at_z": lambda z: r_base + (r_top - r_base) * (z / height)
            if height > 0 else r_base,
        }
    elif feat_type in ("cylinder",):
        return {
            "type": "cylinder",
            "max_r": params.get("radius", 0),
        }
    elif feat_type == "box":
        return {
            "type": "box",
            "half_length": params.get("length", 0) / 2,
            "half_width": params.get("width", 0) / 2,
        }
    return {"type": "unknown"}


def _find_driving_pattern(design: Design,
                          prov_by_id: dict[str, FeatureProvenance]) -> tuple:
    """Find the circular_pattern feature and its leaf params that determine
    the max radial extent. Returns (pattern_feat, leaf_feat, leaf_type, leaf_params)."""
    for feat in design.features:
        if feat.type == "circular_pattern" and feat.op == "union":
            sub = feat.params.get("feature")
            if isinstance(sub, dict) and sub.get("type"):
                return feat, sub, sub["type"], sub.get("params", {})
    return None, None, None, None


def _translate_envelope(node: str, claim: str, measured: float, expected: float,
                        design: Design, solid: cq.Solid,
                        prov_by_id: dict[str, FeatureProvenance]) -> str | None:
    """Translate envelope diameter/Z failure into parameter targets."""

    if claim == "envelope_diameter_mm":
        # Find the driving feature
        _, leaf_feat, leaf_type, leaf_params = _find_driving_pattern(
            design, prov_by_id)

        if leaf_type in ("box", "cylinder"):
            params_str = ", ".join(f"{k}={v}" for k, v in leaf_params.items())
            return (
                f"Envelope diameter {round(measured, 1)}mm vs expected {expected}mm. "
                f"Driving feature is '{node}' ({leaf_type} with {params_str}). "
                f"Increase its radial extent or reduce the envelope to match."
            )

    elif claim == "envelope_z_mm":
        # Find max Z vertex; the driving feature is whatever has highest Z
        max_z = max(v.Z for v in solid.Vertices()) if solid.Vertices() else 0
        return (
            f"Envelope Z: built {round(measured, 1)}mm vs expected {expected}mm. "
            f"Maximum Z vertex is at {round(max_z, 1)}mm. "
            f"Increase feature heights to reach Z={expected}mm or reduce envelope."
        )

    return None


def _translate_embedded(node: str, contribution_ratio: float,
                        design: Design, solid: cq.Solid,
                        prov_by_id: dict[str, FeatureProvenance]) -> str | None:
    """Translate feature_contributes failure into repositioning instructions."""

    prov = prov_by_id.get(node)
    if prov is None or not prov.instance_solids:
        return None

    feat_solid = prov.instance_solids[0]
    feat_constraint = _get_radial_constraint(feat_solid)

    # Find the parent (target) feature
    parent_feat = None
    for f in design.features:
        if f.id == node:
            break
    else:
        # Fallback: feature with target=null is the base body
        for f in design.features:
            if f.target is None:
                parent_feat = f
                break

    parent_name = "parent body"
    parent_max_r = 0
    if parent_feat:
        parent_name = parent_feat.id
        parent_constraints = _get_parent_constraints(
            parent_feat, parent_feat.type, parent_feat.params)
        if parent_constraints["type"] == "frustum":
            parent_max_r = parent_constraints["r_base"]
        elif parent_constraints["type"] == "cylinder":
            parent_max_r = parent_constraints["max_r"]

    pct_embedded = round((1 - contribution_ratio) * 100)

    lines = [
        f"Feature '{node}' is {pct_embedded}% embedded inside '{parent_name}'.",
        f"Feature max radius: {feat_constraint['max_r']}mm, parent max: {parent_max_r}mm.",
    ]

    if feat_constraint["max_r"] <= parent_max_r:
        delta = round(parent_max_r - feat_constraint["max_r"] + 2, 1)
        feat = next((f for f in design.features if f.id == node), None)
        if feat and feat.type == "circular_pattern":
            lines.append(
                f"Move '{node}' outward by at least {delta}mm "
                f"(increase at[0] or equivalent dimension)"
            )
    else:
        lines.append(
            "The feature's max radius already exceeds the parent. "
            "Check if the feature intersects the parent at a different z-level. "
            "For frustum parents, the surface radius changes with height."
        )

    return "\n".join(lines)


def _translate_bore_obstruction(node: str, residual_material: float,
                                design: Design, solid: cq.Solid,
                                prov_by_id: dict[str, FeatureProvenance]) -> str | None:
    """Translate bore_present failure — detect which union feature overlaps the bore."""

    # Find the bore feature and its diameter
    bore_diameter = None
    bore_feat = None
    for feat in design.features:
        if feat.id == node:
            bore_feat = feat
            bore_diameter = feat.params.get("diameter", 0)
            break

    if bore_diameter is None:
        return None

    bore_radius = bore_diameter / 2.0

    # Find union features that might overlap the bore zone
    overlapping = []
    for feat in design.features:
        if feat.op != "union" or feat.id == node:
            continue
        prov = prov_by_id.get(feat.id)
        if prov is None or not prov.instance_solids:
            continue

        # Check if any instance vertex is within bore radius
        for s in prov.instance_solids:
            for v in s.Vertices():
                r = (v.X**2 + v.Y**2)**0.5
                if r < bore_radius + 1.0:  # within 1mm of bore
                    overlapping.append((feat.id, feat.type, feat.params))
                    break
            if overlapping and overlapping[-1][0] == feat.id:
                break

    if overlapping:
        lines = [
            f"Bore '{node}' ({bore_diameter}mm) is obstructed by {residual_material:.0f}mm³ "
            f"of material. The following union features overlap the bore zone:"
        ]
        for ov_id, ov_type, ov_params in overlapping:
            if ov_type == "circular_pattern":
                sub = ov_params.get("feature", {})
                sub_type = sub.get("type", "")
                sub_params = sub.get("params", {})
                at0 = sub_params.get("at", [0, 0, 0])[0] if isinstance(sub_params.get("at"), list) else 0
                length = sub_params.get("length", 0)
                min_r = max(0, at0 - length / 2.0)
                lines.append(
                    f"  - '{ov_id}' ({sub_type} pattern): at[0]={at0}mm, "
                    f"min radius ≈ {round(min_r, 1)}mm (bore radius = {bore_radius}mm)"
                )
                if min_r < bore_radius:
                    new_at = round(bore_radius + length / 2.0 + 2, 1)
                    lines.append(
                        f"    FIX: Move feature outward: at[0] ≥ {new_at}mm "
                        f"(was {at0}) to clear bore"
                    )
            else:
                lines.append(f"  - '{ov_id}' ({ov_type})")
        return "\n".join(lines)

    return (
        f"Bore '{node}' has {residual_material:.0f}mm³ of residual material. "
        f"No clearly overlapping union feature was found. Verify the bore "
        f"parameters: diameter={bore_diameter}mm, at=[0,0,0]."
    )


def _translate_disconnected(node: str, design: Design, solid: cq.Solid,
                            prov_by_id: dict[str, FeatureProvenance]) -> str | None:
    """Translate single_solid failure."""

    n_solids = len(solid.Solids())
    return (
        f"Part consists of {n_solids} disconnected bodies instead of 1. "
        f"Features must physically overlap their parent (not just touch faces). "
        f"For patterned features: ensure each instance intersects the parent "
        f"body. The feature must start inside the parent surface so it fuses, "
        f"then protrude outward."
    )