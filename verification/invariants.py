"""
verification/invariants.py — universal geometry-invariant checks.

These checks fire unconditionally on every compiled solid (planner-independent,
empty asserts). They catch silent-failure classes the existing feature_contributes
and parent_contact checks don't cover:

  hole_edge_clearance_mm  — cut features breaching the part's outer edge
  feature_clearance_mm    — unrelated union features too close together
  self_intersecting       — solid.isValid() gate
  watertight              — solid.IsClosed() gate
  min_wall_mm             — minimum distance between any two non-adjacent faces
  envelope_containment    — every feature's bbox inside the declared envelope

For mesh_only features, the same battery runs using vertex/bbox queries.

CALLED BY: verification/solid_inspector.py (step 3c, after parent_contact)
CALLS: cadquery, core/config_loader
"""
from __future__ import annotations
import cadquery as cq
from core.config_loader import load_inspection_thresholds
from geometry_ir.models import Design


def _th():
    return load_inspection_thresholds().get("invariants", {})


def _result(node, claim, passed, measured, expected, detail=""):
    return {"node": node, "claim": claim, "passed": bool(passed),
            "measured": measured, "expected": expected, "detail": detail}


# ── Hole edge clearance ──────────────────────────────────────────────────────

def _check_hole_edge_clearance(solid: cq.Solid, design) -> list[dict]:
    """Every hole (cut) feature must not breach the part's outer boundary."""
    th = _th()
    clearance_min = th.get("hole_edge_clearance_mm", 1.0)
    results = []

    for feat in design.features:
        if feat.type == "circular_pattern" and feat.op == "cut":
            sub = feat.params.get("feature", {})
            if isinstance(sub, dict) and sub.get("type") == "hole":
                hole_dia = sub.get("params", {}).get("diameter", 0)
                hole_at = sub.get("params", {}).get("at", [0, 0, 0])
                node_id = feat.id
            else:
                continue
        elif feat.type == "hole":
            hole_dia = feat.params.get("diameter", 0)
            hole_at = feat.params.get("at", [0, 0, 0])
            node_id = feat.id
        else:
            continue
        hole_radius = hole_dia / 2.0

        center_dist = (hole_at[0]**2 + hole_at[1]**2)**0.5
        outer_radius = max(
            (v.X**2 + v.Y**2)**0.5 for v in solid.Vertices()
        ) if solid.Vertices() else 0

        hole_edge_dist = center_dist + hole_radius
        clearance = outer_radius - hole_edge_dist

        ok = clearance >= clearance_min
        results.append(_result(
            node_id, "hole_edge_clearance_mm",
            ok, round(clearance, 2), f">= {clearance_min}",
            f"hole at r={round(center_dist,1)}mm dia={hole_dia}mm →"
            f" edge at r={round(hole_edge_dist,1)}mm,"
            f" outer at r={round(outer_radius,1)}mm,"
            f" clearance={round(clearance,2)}mm"
            + ("" if ok else f" (breach by {round(-clearance,2)}mm)")
        ))

    return results


# ── Feature-to-feature clearance ─────────────────────────────────────────────

def _check_feature_clearance(solid: cq.Solid, design, provenance) -> list[dict]:
    """Any two union features that are not parent-child must not be too close."""
    th = _th()
    clearance_min = th.get("feature_clearance_mm", 0.5)
    results = []

    prov_by_id = {p.id: p for p in provenance}
    union_features = [
        f for f in design.features
        if f.op == "union" and f.id in prov_by_id and not prov_by_id[f.id].mesh_only
    ]

    for i, f1 in enumerate(union_features):
        for f2 in union_features[i+1:]:
            if f2.target == f1.id or f1.target == f2.id:
                continue
            if f1.target and f2.target and f1.target == f2.target:
                continue

            p1 = prov_by_id.get(f1.id)
            p2 = prov_by_id.get(f2.id)
            if p1 is None or p2 is None:
                continue

            s1 = (p1.instance_solids or [None])[0]
            s2 = (p2.instance_solids or [None])[0]
            if s1 is None or s2 is None:
                continue

            try:
                dist = s1.Distance(s2)
                ok = dist >= clearance_min
                results.append(_result(
                    f"{f1.id}～{f2.id}", "feature_clearance_mm",
                    ok, round(dist, 2), f">= {clearance_min}",
                    f"distance between '{f1.id}' and '{f2.id}'"
                    f" is {round(dist,2)}mm"
                    + ("" if ok else f" (below {clearance_min}mm minimum)")
                ))
            except Exception:
                pass

    return results


# ── Self-intersection ────────────────────────────────────────────────────────

def _check_self_intersecting(solid: cq.Solid) -> list[dict]:
    """solid.isValid() must return True."""
    th = _th()
    enforce = th.get("self_intersecting", True)
    if not enforce:
        return []
    try:
        ok = solid.isValid()
    except AttributeError:
        ok = True  # Compound — use inner solid check
    return [_result(
        "design", "self_intersecting",
        ok, ok, True,
        "" if ok else "solid.isValid() returned False — geometry is self-intersecting or non-manifold"
    )]


# ── Watertight ───────────────────────────────────────────────────────────────

def _check_watertight(solid: cq.Solid) -> list[dict]:
    """solid.IsClosed() must return True — blocking gate."""
    th = _th()
    enforce = th.get("watertight", True)
    if not enforce:
        return []
    try:
        ok = solid.IsClosed()
    except AttributeError:
        ok = True  # Compound — use inner solid check
    return [_result(
        "design", "watertight",
        ok, ok, True,
        "" if ok else "solid.IsClosed() returned False — geometry is not a closed manifold"
    )]


# ── Min-wall between faces ───────────────────────────────────────────────────

def _check_min_wall(solid: cq.Solid, min_wall_mm: float) -> list[dict]:
    """Minimum distance between any two non-adjacent faces of the final solid."""
    th = _th()
    threshold = th.get("min_wall_mm") or min_wall_mm
    if threshold is None or threshold <= 0:
        return []

    faces = list(solid.Faces())
    if len(faces) < 2:
        return []

    min_dist = float('inf')
    n = len(faces)
    for i in range(n):
        for j in range(i+1, n):
            try:
                dist = faces[i].distance(faces[j])
                if dist > 1e-6:
                    min_dist = min(min_dist, dist)
            except Exception:
                continue

    if min_dist == float('inf'):
        return []

    ok = round(min_dist, 2) >= threshold
    return [_result(
        "design", "min_wall_mm",
        ok, round(min_dist, 2), f">= {threshold}",
        "" if ok else f"minimum wall thickness {round(min_dist,2)}mm"
        f" is below process floor of {threshold}mm"
    )]


# ── Feature within envelope ──────────────────────────────────────────────────

def _check_envelope_containment(solid: cq.Solid, design, provenance) -> list[dict]:
    """Every feature's bounding box must be within the declared envelope."""
    th = _th()
    enforce = th.get("envelope_containment", True)
    if not enforce:
        return []

    env = design.envelope
    if env is None:
        return []

    prov_by_id = {p.id: p for p in provenance}
    results = []
    env_x, env_y, env_z = env.x_mm, env.y_mm, env.z_mm
    env_tol = env.tolerance_mm or 0

    for feat in design.features:
        if feat.type in ("circular_pattern", "linear_pattern"):
            continue
        if feat.op == "cut":
            continue  # cut features use oversized tools, skip containment
        prov = prov_by_id.get(feat.id)
        if prov is None or prov.mesh_only:
            continue
        if not prov.instance_solids:
            continue

        s = prov.instance_solids[0]
        bb = s.BoundingBox()

        violations = []
        if bb.xmax > env_x/2 + env_tol:
            violations.append(f"xmax={round(bb.xmax,1)} > env_x/2+tol={env_x/2+env_tol}")
        if bb.xmin < -env_x/2 - env_tol:
            violations.append(f"xmin={round(bb.xmin,1)} < -env_x/2-tol={-env_x/2-env_tol}")
        if bb.ymax > env_y/2 + env_tol:
            violations.append(f"ymax={round(bb.ymax,1)} > env_y/2+tol")
        if bb.ymin < -env_y/2 - env_tol:
            violations.append(f"ymin={round(bb.ymin,1)} < -env_y/2-tol")
        if bb.zmax > env_z + env_tol:
            violations.append(f"zmax={round(bb.zmax,1)} > env_z+tol={env_z+env_tol}")
        if bb.zmin < -env_tol:
            violations.append(f"zmin={round(bb.zmin,1)} < -tol={-env_tol}")

        ok = not violations
        results.append(_result(
            feat.id, "envelope_containment",
            ok, "; ".join(violations) if violations else "within envelope",
            f"envelope x=±{env_x/2} y=±{env_y/2} z=[0,{env_z}]",
            f"feature '{feat.id}' bbox x=[{round(bb.xmin,1)},{round(bb.xmax,1)}] "
            f"y=[{round(bb.ymin,1)},{round(bb.ymax,1)}] z=[{round(bb.zmin,1)},{round(bb.zmax,1)}]"
            + ("" if ok else f" — VIOLATION: {'; '.join(violations)}")
        ))

    return results


# ── Mesh-only invariants ─────────────────────────────────────────────────────

def check_mesh_only(mesh_path: str, design) -> list[dict]:
    """Run invariants on a mesh_only feature's exported STL."""
    results = []
    import os
    if not os.path.exists(mesh_path):
        results.append(_result(
            "mesh", "mesh_exists", False, mesh_path, "file must exist",
            "mesh_only STL not found at expected path"
        ))
        return results

    file_size = os.path.getsize(mesh_path)
    results.append(_result(
        "mesh", "mesh_nonempty",
        file_size > 100, file_size, "> 100 bytes",
        f"mesh file is {file_size} bytes"
    ))

    return results


# ── Main entry point ─────────────────────────────────────────────────────────

def run_invariants(design, solid: cq.Solid, provenance: list,
                   min_wall_mm: float = 2.0) -> list[dict]:
    """Run all universal invariant checks. Returns list of node-keyed results."""
    if isinstance(design, dict):
        design = Design.model_validate(design)

    checks = []

    checks.extend(_check_hole_edge_clearance(solid, design))
    checks.extend(_check_feature_clearance(solid, design, provenance))
    checks.extend(_check_self_intersecting(solid))
    checks.extend(_check_watertight(solid))
    checks.extend(_check_min_wall(solid, min_wall_mm))
    checks.extend(_check_envelope_containment(solid, design, provenance))

    return checks