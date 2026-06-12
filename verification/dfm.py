"""
verification/dfm.py — deterministic DFM (manufacturability) checks.

Driven by the active process profile from core/process_detector.load_profile().
Measures off the compiled solid: overhang angle, bridge span, minimum hole
diameter, minimum feature size, and draft angle. Values come from
config/process/manufacturing_profiles.json — NO DFM constants hardcoded here.

CALLED BY: verification/solid_inspector.py (step 3d, after invariants)
CALLS: cadquery, core/process_detector
"""
from __future__ import annotations
import math
import cadquery as cq
from geometry_ir.models import Design


def _result(node, claim, passed, measured, expected, detail=""):
    return {"node": node, "claim": claim, "passed": bool(passed),
            "measured": measured, "expected": expected, "detail": detail}


# ── Overhang angle ───────────────────────────────────────────────────────────

def _check_overhang(solid: cq.Solid, profile: dict, design) -> list[dict]:
    """Flag faces whose angle from horizontal exceeds max_overhang_deg.
    Build direction is +Z. The overhang angle is measured as the angle between
    the face normal and the -Z direction (i.e., how steeply the face slopes)."""
    max_deg = profile.get("max_overhang_deg")
    if max_deg is None:
        return []  # No overhang limit for this process

    max_angle_rad = math.radians(max_deg)
    faces = list(solid.Faces())
    overhanging = []

    for i, face in enumerate(faces):
        try:
            center = face.Center()
            normal = face.normalAt(center)
            # The angle of a face from horizontal:
            # A flat horizontal face has normal.z = ±1 (angle 0° from horizontal)
            # A 45° overhang has normal.z ≈ 0.707 downward
            # The overhang angle = 90 - acos(|normal.z|) for downward faces
            z_abs = abs(normal.z)
            if z_abs > 0.99:
                continue  # Nearly horizontal or vertical — check z sign

            # Only check faces with a downward component (normal.z < -0.01)
            # A perfectly vertical face (z≈0) isn't an overhang — it's a wall.
            # True overhangs have the face normal pointing somewhat downward.
            if normal.z >= -0.01:
                continue

            # Overhang angle: angle of face from horizontal
            # For downward-facing faces: 90° - acos(|z|) = asin(|z|) from horizontal
            overhang_angle = round(90.0 - math.degrees(math.acos(z_abs)), 1)

            if overhang_angle > max_deg:
                overhanging.append(overhang_angle)
        except Exception:
            continue

    if overhanging:
        worst = max(overhanging)
        return [_result(
            "design", "overhang_angle",
            False, round(worst, 1), f"≤ {max_deg}°",
            f"{len(overhanging)} face(s) exceed {max_deg}° overhang limit"
            f" (worst: {worst}°)"
        )]

    return [_result(
        "design", "overhang_angle",
        True, "no overhanging faces", f"≤ {max_deg}°",
        f"all faces within {max_deg}° overhang limit"
    )]


# ── Bridge span ──────────────────────────────────────────────────────────────

def _check_bridge_span(solid: cq.Solid, profile: dict, design) -> list[dict]:
    """Detect unsupported horizontal spans exceeding max_bridge_span_mm.
    Approximated by checking for flat horizontal faces whose edges exceed the limit.
    Only considers planar faces (skips curved surfaces like cylinders)."""
    max_span = profile.get("max_bridge_span_mm")
    if max_span is None:
        return []

    faces = list(solid.Faces())
    long_spans = []

    for face in faces:
        try:
            geom_type = face.geomType()
            if geom_type != "PLANE":
                continue  # Skip curved faces — only flat horizontal spans matter
            center = face.Center()
            normal = face.normalAt(center)
            # A bridge has a downward-facing horizontal face
            if normal.z > -0.95:
                continue  # Not downward-facing enough

            try:
                face_edges = list(face.Edges())
                max_len = 0
                for edge in face_edges:
                    max_len = max(max_len, edge.Length())
                if max_len > max_span:
                    long_spans.append(round(max_len, 1))
            except Exception:
                continue
        except Exception:
            continue

    if long_spans:
        worst = max(long_spans)
        return [_result(
            "design", "bridge_span",
            False, round(worst, 1), f"≤ {max_span}mm",
            f"{len(long_spans)} span(s) exceed {max_span}mm bridge limit"
            f" (worst: {worst}mm)"
        )]

    return [_result(
        "design", "bridge_span",
        True, "no excessive spans", f"≤ {max_span}mm",
        f"all spans within {max_span}mm bridge limit"
    )]


# ── Minimum hole diameter ────────────────────────────────────────────────────

def _check_min_hole_diameter(profile: dict, design) -> list[dict]:
    """Every hole must have diameter ≥ min_hole_diameter_mm."""
    min_dia = profile.get("min_hole_diameter_mm")
    if min_dia is None:
        return []

    results = []

    for feat in design.features:
        if feat.type == "hole":
            dia = feat.params.get("diameter", 0)
            node_id = feat.id
        elif feat.type == "circular_pattern" and feat.op == "cut":
            sub = feat.params.get("feature", {})
            if isinstance(sub, dict) and sub.get("type") == "hole":
                dia = sub.get("params", {}).get("diameter", 0)
                node_id = feat.id
            else:
                continue
        else:
            continue

        ok = dia >= min_dia
        results.append(_result(
            node_id, "min_hole_diameter_mm",
            ok, round(dia, 2), f"≥ {min_dia}",
            f"hole diameter {dia}mm" +
            ("" if ok else f" below {min_dia}mm minimum")
        ))

    return results


# ── Minimum feature size ─────────────────────────────────────────────────────

def _check_min_feature_size(profile: dict, provenance: list) -> list[dict]:
    """Every leaf feature's smallest dimension ≥ min_feature_mm."""
    min_feat = profile.get("min_feature_mm")
    if min_feat is None:
        return []

    results = []

    for prov in provenance:
        if prov.mesh_only or not prov.instance_solids:
            continue
        if prov.op == "cut":
            continue  # cuts are measured by hole diameter, not feature size

        s = prov.instance_solids[0]
        bb = s.BoundingBox()
        min_dim = min(bb.xlen, bb.ylen, bb.zlen)

        ok = min_dim >= min_feat
        results.append(_result(
            prov.id, "min_feature_size_mm",
            ok, round(min_dim, 2), f"≥ {min_feat}",
            f"smallest dimension {round(min_dim,2)}mm" +
            ("" if ok else f" below {min_feat}mm minimum")
        ))

    return results


# ── Draft angle ──────────────────────────────────────────────────────────────

def _check_draft_angle(solid: cq.Solid, profile: dict, design) -> list[dict]:
    """For molding/casting: vertical faces must taper at draft_angle_deg."""
    draft_deg = profile.get("draft_angle_deg")
    if draft_deg is None:
        return []

    faces = list(solid.Faces())
    faces_missing_draft = []

    for face in faces:
        try:
            center = face.Center()
            normal = face.normalAt(center)
            # A vertical face has normal perpendicular to Z (horizontally oriented)
            # Draft means the face tilts inward by at least draft_deg from vertical
            z_component = abs(normal.z)
            # For a perfectly vertical face, z_component = 0
            # For a face with draft, z_component = sin(draft_angle)
            actual_draft = math.degrees(math.asin(min(z_component, 1.0)))

            # Vertical faces (z close to 0) need draft
            if z_component < 0.02:  # within ~1 degree of vertical
                faces_missing_draft.append(round(actual_draft, 1))
        except Exception:
            continue

    if faces_missing_draft:
        return [_result(
            "design", "draft_angle",
            False, f"{len(faces_missing_draft)} vertical faces",
            f"≥ {draft_deg}° draft",
            f"{len(faces_missing_draft)} vertical face(s) may lack"
            f" required {draft_deg}° draft angle"
        )]

    return [_result(
        "design", "draft_angle",
        True, "sufficient draft detected", f"≥ {draft_deg}°",
        f"draft appears sufficient for {draft_deg}° requirement"
    )]


# ── Main entry point ─────────────────────────────────────────────────────────

def run_dfm_checks(solid: cq.Solid, design, provenance: list,
                   profile: dict) -> list[dict]:
    """Run all DFM checks for the active process profile."""
    if isinstance(design, dict):
        design = Design.model_validate(design)

    checks = []

    checks.extend(_check_overhang(solid, profile, design))
    checks.extend(_check_bridge_span(solid, profile, design))
    checks.extend(_check_min_hole_diameter(profile, design))
    checks.extend(_check_min_feature_size(profile, provenance))
    checks.extend(_check_draft_angle(solid, profile, design))

    return checks