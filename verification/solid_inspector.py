"""
verification/solid_inspector.py — L2 deterministic intent ground truth.

WHAT: inspect_solid(design, solid, provenance, min_wall) reads the compiled solid
      + provenance and checks each result against the IR's DECLARED claims
      (single_solid, envelope/diameter, count, uniform_thickness, taper, bore).
      Every result is node-keyed so the reviewer can issue a surgical repair.

VERDICT CONTRACT (PART A):
  geometrically_valid: bool — driven ONLY by structural/intent checks.
  manufacturable: bool       — driven ONLY by DFM checks for the active process.
  valid: bool                — backwards-compat == geometrically_valid.
  Every check tagged severity: "blocking" | "dfm".

SMART VERIFICATION:
  - Universal `feature_contributes` check: fires for EVERY union feature using
    the compiler's contribution audit data. Catches any embedded feature
    (feature inside body, boss inside box, rib inside shell) without knowing
    what the feature IS.
  - Bore check uses the FINAL SOLID's bounding box, not the oversized cutting
    tool. Prevents false negatives from probes that extend far beyond the part.

CALLED BY: pipeline.py (L2 gate), agents/reviewer_agent (consumes results),
           tests.
CALLS: cadquery; geometry_ir/models.py (Design); primitives/compiler.py
       (compile_design, FeatureProvenance).
`custom`/mesh_only features are skipped here (covered by L3 vision / L4 meshlib).
"""
from __future__ import annotations
import cadquery as cq

from geometry_ir.models import Design
from primitives.compiler import compile_design, FeatureProvenance
from core.config_loader import load_inspection_thresholds
from verification.invariants import run_invariants, check_mesh_only as _check_mesh_only
from verification.dfm import run_dfm_checks

# ── Thresholds loaded from config/checks/inspection_thresholds.yaml ───────────
_th = load_inspection_thresholds()
ENV_REL_TOL = _th["envelope"]["rel_tol"]
_CONTRIB_RATIO_FLOOR = _th["feature_contributes"]["contribution_ratio_floor"]
_THICKNESS_BAND_FRAC = _th["uniform_thickness"]["band_frac"]
_THICKNESS_MIN_BAND = _th["uniform_thickness"]["min_band_mm"]
_CONTACT_GAP_TOL = _th["parent_contact"]["gap_tolerance_mm"]
_BORE_VOID_FRACTION = _th["bore"]["void_volume_fraction"]
_BORE_PROBE_FRACTION = _th["bore"]["probe_diameter_fraction"]

# ── DFM claim set — the fixed contract of which claims are manufacturability ──
# These are advisory (don't gate geometrically_valid).  Changing this requires
# editing the verdict CONTRACT and updating the ground-truth oracle.
DFM_CLAIMS: set[str] = {
    "overhang_angle", "bridge_span", "min_hole_diameter_mm",
    "min_feature_size_mm", "draft_angle",
}


def _result(node, claim, passed, measured, expected, detail="", severity="blocking"):
    return {"node": node, "claim": claim, "passed": bool(passed),
            "measured": measured, "expected": expected, "detail": detail,
            "severity": severity}


def _min_axis_len(bbox: tuple[float, float, float]) -> float:
    return min(bbox)


def inspect_solid(design: Design | dict, solid: cq.Solid,
                  provenance: list[FeatureProvenance], min_wall_mm: float = 2.0,
                  profile: dict | None = None) -> dict:
    """Run L2 checks.

    Returns:
      { geometrically_valid, manufacturable, valid,
        checks: [ {node, claim, passed, measured, expected, detail, severity} ],
        hard_failures: [str] }
    """
    if isinstance(design, dict):
        design = Design.model_validate(design)
    prov_by_id = {p.id: p for p in provenance}
    checks: list[dict] = []

    # ═══════════════════════════════════════════════════════════════════════════
    # 1. Single connected solid (manifold intent).
    # ═══════════════════════════════════════════════════════════════════════════
    n_solids = len(solid.Solids())
    checks.append(_result("design", "single_solid", n_solids == 1, n_solids, 1,
                          "result must be one connected manifold"))

    # ═══════════════════════════════════════════════════════════════════════════
    # 2. Envelope (coarse overall-size bound).
    # ═══════════════════════════════════════════════════════════════════════════
    bb = solid.BoundingBox()
    env = design.envelope

    def _env_check(name, measured, expected):
        eff_tol = max(env.tolerance_mm, ENV_REL_TOL * expected)
        # Envelope is an UPPER BOUND — the part must fit INSIDE it.
        # measured ≤ expected + tol is OK (part fits); measured > expected is
        # only a failure when it exceeds the tolerance band.
        ok = measured <= expected + eff_tol
        checks.append(_result("envelope", name,
                              ok,
                              round(measured, 3), f"≤ {expected}",
                              f"measured={round(measured,3)} vs envelope={expected}"
                              f" (tol +{round(eff_tol, 3)})"))

    has_circular = any(f.type == "circular_pattern" and f.op == "union"
                       for f in design.features)
    if has_circular:
        dia = 2.0 * max((v.X ** 2 + v.Y ** 2) ** 0.5 for v in solid.Vertices())
        _env_check("envelope_diameter_mm", dia, max(env.x_mm, env.y_mm))
        _env_check("envelope_z_mm", bb.zlen, env.z_mm)
    else:
        _env_check("envelope_x_mm", bb.xlen, env.x_mm)
        _env_check("envelope_y_mm", bb.ylen, env.y_mm)
        _env_check("envelope_z_mm", bb.zlen, env.z_mm)

    # ═══════════════════════════════════════════════════════════════════════════
    # 3. Universal feature_contributes (compiler audit data).
    # ═══════════════════════════════════════════════════════════════════════════
    for feat in design.features:
        prov = prov_by_id.get(feat.id)
        if prov is None or prov.mesh_only:
            continue
        if feat.op == "union" and prov.volume > 1.0:
            is_base = (feat == design.features[0] and feat.target is None)
            if not is_base:
                checks.append(_result(
                    feat.id, "feature_contributes",
                    prov.contribution_ratio > _CONTRIB_RATIO_FLOOR,
                    round(prov.contribution_ratio, 4), f"> {_CONTRIB_RATIO_FLOOR}",
                    f"only {prov.contribution_ratio * 100:.0f}% of '{feat.id}' "
                    f"protrudes from the surface ({prov.external_volume:.0f}mm³ "
                    f"of {prov.volume:.0f}mm³ total)"))

    # ═══════════════════════════════════════════════════════════════════════════
    # 3c. Universal invariants.
    # ═══════════════════════════════════════════════════════════════════════════
    checks.extend(run_invariants(design, solid, provenance, min_wall_mm=min_wall_mm))

    # ═══════════════════════════════════════════════════════════════════════════
    # 3d. DFM checks (advisory — tagged severity "dfm").
    # ═══════════════════════════════════════════════════════════════════════════
    if profile is not None:
        dfm_raw = run_dfm_checks(solid, design, provenance, profile)
        for c in dfm_raw:
            c["severity"] = "dfm"
        checks.extend(dfm_raw)

    # ═══════════════════════════════════════════════════════════════════════════
    # 3b. Parent contact check.
    # ═══════════════════════════════════════════════════════════════════════════
    for feat in design.features:
        prov = prov_by_id.get(feat.id)
        if prov is None or prov.mesh_only:
            continue
        if feat.op == "union" and feat.target is not None:
            target_feat = next((f for f in design.features if f.id == feat.target), None)
            if target_feat and target_feat.type in ("frustum", "cone", "cylinder"):
                checks.append(_check_parent_contact(
                    feat.id, prov, target_feat.id, target_feat.type, target_feat.params))

    # ═══════════════════════════════════════════════════════════════════════════
    # 4. Per-feature claims from asserts.
    # ═══════════════════════════════════════════════════════════════════════════
    for feat in design.features:
        prov = prov_by_id.get(feat.id)
        if prov is None or prov.mesh_only:
            continue
        a = feat.asserts or {}

        if "count" in a:
            checks.append(_result(feat.id, "count", prov.instances == a["count"],
                                  prov.instances, a["count"],
                                  "pattern instance count"))

        if "uniform_thickness_mm" in a:
            checks.append(_check_uniform_thickness(feat, prov, a["uniform_thickness_mm"]))

        if "taper" in a:
            checks.append(_check_taper(feat.id, prov, a["taper"]))

        if "bore_diameter_mm" in a:
            checks.append(_check_bore(feat.id, prov, solid, a["bore_diameter_mm"]))

    # ═══════════════════════════════════════════════════════════════════════════
    # 5. Fillet/chamfer verification.
    # ═══════════════════════════════════════════════════════════════════════════
    for feat in design.features:
        if feat.type == "fillet" and feat.op == "fillet":
            declared = feat.params.get("radius", 1.0)
            checks.append(_check_fillet_radius(feat.id, solid, declared))
        elif feat.type == "chamfer" and feat.op == "chamfer":
            declared = feat.params.get("length", 1.0)
            checks.append(_check_chamfer_length(feat.id, solid, declared))

    # ═══════════════════════════════════════════════════════════════════════════
    # VERDICT: split geometrically_valid from manufacturable.
    # ═══════════════════════════════════════════════════════════════════════════
    structural_failures = [
        c for c in checks
        if not c["passed"] and c.get("severity", "blocking") != "dfm"
    ]
    dfm_failures = [
        c for c in checks
        if not c["passed"] and c.get("severity", "blocking") == "dfm"
    ]

    geometrically_valid = len(structural_failures) == 0
    manufacturable = len(dfm_failures) == 0

    return {
        "geometrically_valid": geometrically_valid,
        "manufacturable": manufacturable,
        "valid": geometrically_valid,  # backwards-compat
        "checks": checks,
        "hard_failures": [
            f"{c['node']}.{c['claim']}: measured {c['measured']} expected {c['expected']}"
            for c in structural_failures
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Check helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _thickness_param(ftype: str, params: dict):
    """The declared wall-thickness of a primitive, read from its params. None if
    the primitive has no single explicit thickness dimension (→ fall back to AABB)."""
    if ftype == "box":
        vals = [params.get(k) for k in ("length", "width", "height")]
        return min(v for v in vals if v is not None) if any(vals) else None
    if ftype == "tube":
        if params.get("outer_radius") is not None and params.get("inner_radius") is not None:
            return params["outer_radius"] - params["inner_radius"]
    return None


def _check_uniform_thickness(feat, prov: FeatureProvenance, declared: float,
                             band_frac: float | None = None) -> dict:
    node = feat.id
    sub = feat.params.get("feature") if feat.type in ("circular_pattern", "linear_pattern") else None
    ftype = sub["type"] if isinstance(sub, dict) else feat.type
    fparams = sub.get("params", {}) if isinstance(sub, dict) else feat.params
    measured = _thickness_param(ftype, fparams)
    _bf = band_frac if band_frac is not None else _THICKNESS_BAND_FRAC
    band = max(declared * _bf, _THICKNESS_MIN_BAND)
    if measured is not None:
        ok = abs(measured - declared) <= band
        return _result(node, "uniform_thickness_mm", ok, round(measured, 3), declared,
                       f"declared {ftype} thickness param vs assert (band ±{band:.2f})")
    base = (prov.instance_solids or [None])[0]
    if base is None:
        return _result(node, "uniform_thickness_mm", False, None, declared, "no instance")
    bb = base.BoundingBox()
    measured = _min_axis_len((round(bb.xlen, 4), round(bb.ylen, 4), round(bb.zlen, 4)))
    _bf = band_frac if band_frac is not None else _THICKNESS_BAND_FRAC
    band = max(declared * _bf, _THICKNESS_MIN_BAND)
    ok = abs(measured - declared) <= band
    return _result(node, "uniform_thickness_mm", ok, round(measured, 3), declared,
                   f"base instance min-axis vs declared (band ±{band:.2f})")


def _radial_extent(solid: cq.Solid, z: float, axis_xy=(0.0, 0.0)) -> float:
    best = 0.0
    for v in solid.Vertices():
        if abs(v.Z - z) <= 3.0:
            r = ((v.X - axis_xy[0]) ** 2 + (v.Y - axis_xy[1]) ** 2) ** 0.5
            best = max(best, r)
    return best


def _check_taper(node, prov: FeatureProvenance, direction: str) -> dict:
    s = prov.instance_solids[0]
    bb = s.BoundingBox()
    r_lo = _radial_extent(s, bb.zmin + 1.0)
    r_hi = _radial_extent(s, bb.zmax - 1.0)
    if not isinstance(direction, str):
        direction = "outward_base"
    if direction == "outward_base":
        ok = r_lo >= r_hi - 0.5
    else:
        ok = r_hi >= r_lo - 0.5
    return _result(node, "taper", ok, {"r_base": round(r_lo, 2), "r_top": round(r_hi, 2)},
                   direction, "radial protrusion direction base→top")


def _check_parent_contact(node: str, prov: FeatureProvenance, parent_id: str,
                           parent_type: str, parent_params: dict) -> dict:
    if not prov.instance_solids:
        return _result(node, "parent_contact", False, "no instances", "must intersect parent",
                       "feature has no geometry instances")
    feat_solid = prov.instance_solids[0]
    feat_bb = feat_solid.BoundingBox()
    z_min = feat_bb.zmin
    z_max = feat_bb.zmax
    min_r_at_bottom = float('inf')
    min_r_at_top = float('inf')
    for v in feat_solid.Vertices():
        r = (v.X**2 + v.Y**2)**0.5
        if abs(v.Z - z_min) <= 3.0:
            min_r_at_bottom = min(min_r_at_bottom, r)
        if abs(v.Z - z_max) <= 3.0:
            min_r_at_top = min(min_r_at_top, r)
    if parent_type in ("frustum", "cone"):
        r_base = parent_params.get("r_base", 0)
        r_top = parent_params.get("r_top", 0)
        height = parent_params.get("height", 1.0)
        parent_r_at_bottom = r_base + (r_top - r_base) * ((z_min - 0) / height) if height > 0 else r_base
        parent_r_at_top = r_base + (r_top - r_base) * ((z_max - 0) / height) if height > 0 else r_base
    elif parent_type == "cylinder":
        parent_r_at_bottom = parent_params.get("radius", 0)
        parent_r_at_top = parent_r_at_bottom
    else:
        return _result(node, "parent_contact", True, "skipped",
                       f"{parent_type} parent",
                       f"parent_contact check not implemented for {parent_type}")
    detachment_zones = []
    if min_r_at_bottom != float('inf') and min_r_at_bottom > parent_r_at_bottom + _CONTACT_GAP_TOL:
        detachment_zones.append(f"z≈{round(z_min,1)}mm: feature min_r={round(min_r_at_bottom,1)}mm "
                                f"> parent r={round(parent_r_at_bottom,1)}mm")
    if min_r_at_top != float('inf') and min_r_at_top > parent_r_at_top + _CONTACT_GAP_TOL:
        detachment_zones.append(f"z≈{round(z_max,1)}mm: feature min_r={round(min_r_at_top,1)}mm "
                                f"> parent r={round(parent_r_at_top,1)}mm")
    has_contact = not detachment_zones
    detail = ("feature fully contacts parent across height"
              if has_contact else "; ".join(detachment_zones) +
              " — feature detaches from parent, producing corrupted geometry")
    return _result(node, "parent_contact", has_contact,
                   {"detachment_zones": detachment_zones, "z_range": [round(z_min, 1), round(z_max, 1)]},
                   "full height contact with parent", detail)


def _check_bore(node, prov: FeatureProvenance, solid: cq.Solid, diameter: float) -> dict:
    bb = solid.BoundingBox()
    probe = cq.Solid.makeCylinder(diameter / 2.0 * _BORE_PROBE_FRACTION, bb.zlen + 4,
                                  cq.Vector(0, 0, bb.zmin - 2))
    void_vol = solid.intersect(probe).Volume()
    ok = void_vol < probe.Volume() * _BORE_VOID_FRACTION
    return _result(node, "bore_present", ok, round(void_vol, 2), 0.0,
                   f"residual material inside bore dia {diameter}mm")


# ═══════════════════════════════════════════════════════════════════════════════
# Fillet / chamfer measurement — from actual geometry (C1)
# ═══════════════════════════════════════════════════════════════════════════════

def _check_fillet_radius(node: str, solid: cq.Solid, declared_radius: float) -> dict:
    """Measure realized fillet radius from actual edge geometry.

    Fillets create curved edges on the solid.  Scan all edges, try edge.radius()
    (works on CIRCLE arcs and some spline-based edges).  Falls back to a
    volume/bbox heuristic only when no edge reports a radius.
    Tolerance: ±25% or ±1.0mm, whichever is larger.
    """
    # Strategy 1: scan every edge for a measurable radius
    measured_r = None
    best_deviation = float('inf')
    for edge in solid.Edges():
        try:
            r = edge.radius()
            if 0.1 < r < 500:
                dev = abs(r - declared_radius)
                if dev < best_deviation:
                    best_deviation = dev
                    measured_r = r
        except Exception:
            continue

    # Strategy 2: try face radius via cylindrical face edges
    if measured_r is None:
        for face in solid.Faces():
            try:
                if face.geomType() == "CYLINDER":
                    # Cylindrical faces on fillets have circular edges
                    # whose radius equals the fillet radius.
                    for edge in face.Edges():
                        try:
                            r = edge.radius()
                            if 0.1 < r < 500:
                                dev = abs(r - declared_radius)
                                if dev < best_deviation:
                                    best_deviation = dev
                                    measured_r = r
                        except Exception:
                            continue
                    if measured_r is not None:
                        break  # found a good measurement from this face
            except Exception:
                continue

    # Strategy 3: volume/bbox fallback
    if measured_r is None:
        bb = solid.BoundingBox()
        vol = solid.Volume()
        dims = sorted([bb.xlen, bb.ylen, bb.zlen])
        if vol > 0 and dims[1] > 0 and dims[2] > 0:
            estimated_orig_min = vol / (dims[1] * dims[2])
            measured_r = (estimated_orig_min - dims[0]) / 2.0
        else:
            measured_r = 0.0

    tol = max(declared_radius * 0.25, 1.0)
    ok = abs(measured_r - declared_radius) <= tol
    return _result(node, "fillet_radius_mm", ok,
                   round(measured_r, 3), declared_radius,
                   f"measured fillet radius {measured_r:.3f}mm vs declared {declared_radius}mm"
                   f" (tol ±{tol:.2f}mm)"
                   + ("" if ok else f" — deviation {abs(measured_r - declared_radius):.3f}mm"))


def _check_chamfer_length(node: str, solid: cq.Solid, declared_length: float) -> dict:
    """Measure realized chamfer length from volume-to-bbox ratio.

    For a box with all edges chamfered, bbox = original - 2*c.
    Tolerance: ±35% or ±1.0mm, whichever is larger.
    """
    bb = solid.BoundingBox()
    vol = solid.Volume()
    dims = sorted([bb.xlen, bb.ylen, bb.zlen])
    measured_c = 0.0
    if vol > 0 and dims[1] > 0 and dims[2] > 0:
        estimated_orig_min = vol / (dims[1] * dims[2])
        measured_c = (estimated_orig_min - dims[0]) / 2.0
    tol = max(declared_length * 0.35, 1.0)
    ok = abs(measured_c - declared_length) <= tol
    return _result(node, "chamfer_length_mm", ok,
                   round(measured_c, 3), declared_length,
                   f"estimated chamfer {measured_c:.3f}mm from bbox"
                   f" (tol ±{tol:.2f}mm)"
                   + ("" if ok else f" — deviation {abs(measured_c - declared_length):.3f}mm"))


def inspect_ir(design: Design | dict, min_wall_mm: float = 2.0,
               profile: dict | None = None) -> dict:
    """Convenience: compile then inspect (used in tests/demo)."""
    if isinstance(design, dict):
        design = Design.model_validate(design)
    solid, prov = compile_design(design)
    if profile is None:
        from core.process_detector import load_profile
        profile = load_profile(design.process)
    return inspect_solid(design, solid, prov, min_wall_mm, profile=profile)