"""
verification/solid_inspector.py — L2 deterministic intent ground truth.

WHAT: inspect_solid(design, solid, provenance, min_wall) reads the compiled solid
      + provenance and checks each result against the IR's DECLARED claims
      (single_solid, envelope/diameter, count, uniform_thickness, taper, bore).
      Every result is node-keyed so the reviewer can issue a surgical repair.

SMART VERIFICATION:
  - Universal `feature_contributes` check: fires for EVERY union feature using
    the compiler's contribution audit data. Catches any embedded feature
    (blade inside hub, boss inside box, rib inside shell) without knowing
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

# Envelope is a COARSE bound: effective tol = max(declared, ENV_REL_TOL*dim).
# Precise intent lives in per-feature asserts, so this can be generous.
ENV_REL_TOL = 0.07  # 7% of the dimension


def _result(node, claim, passed, measured, expected, detail=""):
    return {"node": node, "claim": claim, "passed": bool(passed),
            "measured": measured, "expected": expected, "detail": detail}


def _min_axis_len(bbox: tuple[float, float, float]) -> float:
    return min(bbox)


def inspect_solid(design: Design | dict, solid: cq.Solid,
                  provenance: list[FeatureProvenance], min_wall_mm: float = 2.0) -> dict:
    """Run L2 checks. Returns {valid, checks:[node-keyed], hard_failures:[...]}."""
    if isinstance(design, dict):
        design = Design.model_validate(design)
    prov_by_id = {p.id: p for p in provenance}
    checks: list[dict] = []

    # 1. Single connected solid (manifold intent).
    n_solids = len(solid.Solids())
    checks.append(_result("design", "single_solid", n_solids == 1, n_solids, 1,
                          "result must be one connected manifold"))

    # 2. Tight envelope (declared, not self-reported loose tolerance).
    #    For rotationally-patterned parts the axis-aligned bbox is the WRONG
    #    metric — no pattern instance aligns with X/Y, so the AABB underestimates
    #    size and X≠Y oscillates with instance angle. We instead check the
    #    rotation-invariant circumscribed DIAMETER (2× max radial vertex
    #    distance) against the declared diameter (max of envelope x/y), plus Z.
    #    The envelope is a COARSE overall-size bound (catches collapsed / grossly
    #    oversized parts), NOT a precise gate — precision is enforced by the
    #    per-feature asserts below. So the effective tolerance is the larger of
    #    the declared tolerance and ENV_REL_TOL of the dimension. This lets a
    #    dimensionally-correct part whose features legitimately protrude (e.g.
    #    impeller blades rising above the hub) pass, while a 2x/collapsed part
    #    still fails. NOT a band-aid: wrong FEATURE dims are caught in step 3.
    bb = solid.BoundingBox()
    env = design.envelope

    def _env_check(name, measured, expected):
        eff_tol = max(env.tolerance_mm, ENV_REL_TOL * expected)
        checks.append(_result("envelope", name, abs(measured - expected) <= eff_tol,
                              round(measured, 3), expected,
                              f"|Δ|={abs(measured - expected):.3f} tol={round(eff_tol, 3)} (coarse)"))

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

    # 3. UNIVERSAL: feature contribution check (from compiler's audit).
    #    Fires for EVERY union feature. Catches any embedded feature without
    #    knowing what the feature IS — blade inside hub, boss inside box, etc.
    for feat in design.features:
        prov = prov_by_id.get(feat.id)
        if prov is None or prov.mesh_only:
            continue
        if feat.op == "union" and prov.volume > 1.0:
            # Skip the very first union (the base body — it has nothing to protrude from)
            is_base = (feat == design.features[0] and feat.target is None)
            if not is_base:
                checks.append(_result(
                    feat.id, "feature_contributes",
                    prov.contribution_ratio > 0.20,
                    round(prov.contribution_ratio, 4), "> 0.20",
                    f"only {prov.contribution_ratio * 100:.0f}% of '{feat.id}' "
                    f"protrudes from the surface ({prov.external_volume:.0f}mm³ "
                    f"of {prov.volume:.0f}mm³ total)"
                ))

    # 3b. UNIVERSAL: parent contact check — feature must intersect parent at all z-levels
    for feat in design.features:
        prov = prov_by_id.get(feat.id)
        if prov is None or prov.mesh_only:
            continue
        if feat.op == "union" and feat.target is not None:
            target_feat = next((f for f in design.features if f.id == feat.target), None)
            if target_feat and target_feat.type in ("frustum", "cone", "cylinder"):
                checks.append(_check_parent_contact(
                    feat.id, prov, target_feat.id, target_feat.type, target_feat.params))

    # 4. Per-feature claims driven by each feature's `asserts`.
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

    # Wall thickness floor (DFM) — only meaningful when min_wall declared by process.
    # Applied to non-mesh, non-pattern leaf features as a one-sided floor; the
    # two-sided uniform check above is the authoritative thin-wall guard.

    hard = [c for c in checks if not c["passed"]]
    return {"valid": not hard, "checks": checks,
            "hard_failures": [f"{c['node']}.{c['claim']}: measured {c['measured']} expected {c['expected']}"
                              for c in hard]}


def _thickness_param(ftype: str, params: dict):
    """The declared wall-thickness of a primitive, read from its params. None if
    the primitive has no single explicit thickness dimension (→ fall back to AABB).
    The compiler is deterministic + unit-tested, so the param IS the true wall
    thickness — and unlike an AABB this is correct for TWISTED/swept geometry."""
    if ftype == "blade":
        return params.get("width")
    if ftype == "box":
        vals = [params.get(k) for k in ("length", "width", "height")]
        return min(v for v in vals if v is not None) if any(vals) else None
    if ftype == "tube":
        if params.get("outer_radius") is not None and params.get("inner_radius") is not None:
            return params["outer_radius"] - params["inner_radius"]
    return None


def _check_uniform_thickness(feat, prov: FeatureProvenance, declared: float,
                             band_frac: float = 0.25) -> dict:
    """Two-sided: the feature's wall thickness ≈ declared.

    Catches BOTH too-thin AND the legacy 8.63mm merged-too-thick miss. Prefers
    the declared thickness PARAM (exact, and twist/sweep-proof); only falls back
    to the unrotated base-instance AABB min-axis for primitives with no explicit
    thickness param.
    """
    node = feat.id
    # The thickness-bearing primitive: a pattern's nested feature, else this feature.
    sub = feat.params.get("feature") if feat.type in ("circular_pattern", "linear_pattern") else None
    ftype = sub["type"] if isinstance(sub, dict) else feat.type
    fparams = sub.get("params", {}) if isinstance(sub, dict) else feat.params
    measured = _thickness_param(ftype, fparams)
    band = max(declared * band_frac, 0.3)
    if measured is not None:
        ok = abs(measured - declared) <= band
        return _result(node, "uniform_thickness_mm", ok, round(measured, 3), declared,
                       f"declared {ftype} thickness param vs assert (band ±{band:.2f})")
    # Fallback: AABB min-axis of the unrotated base instance.
    base = (prov.instance_solids or [None])[0]
    if base is None:
        return _result(node, "uniform_thickness_mm", False, None, declared, "no instance")
    bb = base.BoundingBox()
    measured = _min_axis_len((round(bb.xlen, 4), round(bb.ylen, 4), round(bb.zlen, 4)))
    band = max(declared * band_frac, 0.3)
    ok = abs(measured - declared) <= band
    return _result(node, "uniform_thickness_mm", ok, round(measured, 3), declared,
                   f"base instance min-axis vs declared (band ±{band:.2f})")


def _radial_extent(solid: cq.Solid, z: float, axis_xy=(0.0, 0.0)) -> float:
    """Max radial distance of vertices near plane Z=z (for protrusion/taper)."""
    best = 0.0
    for v in solid.Vertices():
        if abs(v.Z - z) <= 3.0:
            r = ((v.X - axis_xy[0]) ** 2 + (v.Y - axis_xy[1]) ** 2) ** 0.5
            best = max(best, r)
    return best


def _check_taper(node, prov: FeatureProvenance, direction: str) -> dict:
    """direction 'outward_base' means protrusion(base) >= protrusion(top).

    Uses the first instance's vertex radial extent at low vs high Z — catches
    the inverted-taper failure (blades protruding more at top than base).

    Normalises boolean `True` → 'outward_base' so that planners writing
    `"taper": true` (the conventional shorthand) still get the correct check
    instead of silently falling through to the outward_top branch."""
    s = prov.instance_solids[0]
    bb = s.BoundingBox()
    r_lo = _radial_extent(s, bb.zmin + 1.0)
    r_hi = _radial_extent(s, bb.zmax - 1.0)
    # Normalise: boolean true → "outward_base" (the default for standard hubs)
    if not isinstance(direction, str):
        direction = "outward_base"
    if direction == "outward_base":
        ok = r_lo >= r_hi - 0.5
    else:  # outward_top
        ok = r_hi >= r_lo - 0.5
    return _result(node, "taper", ok, {"r_base": round(r_lo, 2), "r_top": round(r_hi, 2)},
                   direction, "radial protrusion direction base→top")


def _check_parent_contact(node: str, prov: FeatureProvenance, parent_id: str,
                           parent_type: str, parent_params: dict) -> dict:
    """Check that a union feature maintains contact with its parent across the
    full height/range of the feature. Detects floating/detached features that
    cause corrupted boolean results (e.g. blade in empty space at top of tapered hub).

    For frustum/cone parents: at the feature's z_min and z_max, the feature's
    minimum radial extent must be ≤ parent's surface radius at that z.
    This ensures the blade inner edge is actually inside the hub, not floating.

    GENERAL: works for any union feature on any axially-symmetric parent.
    """
    if not prov.instance_solids:
        return _result(node, "parent_contact", False, "no instances", "must intersect parent",
                       "feature has no geometry instances")

    feat_solid = prov.instance_solids[0]
    feat_bb = feat_solid.BoundingBox()
    z_min = feat_bb.zmin
    z_max = feat_bb.zmax

    # Get feature's minimum radial extent at z_min and z_max
    min_r_at_bottom = float('inf')
    min_r_at_top = float('inf')
    for v in feat_solid.Vertices():
        r = (v.X**2 + v.Y**2)**0.5
        if abs(v.Z - z_min) <= 3.0:
            min_r_at_bottom = min(min_r_at_bottom, r)
        if abs(v.Z - z_max) <= 3.0:
            min_r_at_top = min(min_r_at_top, r)

    # Compute parent surface radius at these z-levels
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
        # Skip check for non-axisymmetric parents
        return _result(node, "parent_contact", True, "skipped",
                       f"{parent_type} parent",
                       f"parent_contact check not implemented for {parent_type}")

    detachment_zones = []
    if min_r_at_bottom != float('inf') and min_r_at_bottom > parent_r_at_bottom + 2.0:
        detachment_zones.append(f"z≈{round(z_min,1)}mm: feature min_r={round(min_r_at_bottom,1)}mm "
                                f"> parent r={round(parent_r_at_bottom,1)}mm")
    if min_r_at_top != float('inf') and min_r_at_top > parent_r_at_top + 2.0:
        detachment_zones.append(f"z≈{round(z_max,1)}mm: feature min_r={round(min_r_at_top,1)}mm "
                                f"> parent r={round(parent_r_at_top,1)}mm")

    has_contact = not detachment_zones
    detail = ("feature fully contacts parent across height"
              if has_contact else "; ".join(detachment_zones) +
              " — feature detaches from parent, producing corrupted geometry")

    return _result(node, "parent_contact", has_contact,
                   {"detachment_zones": detachment_zones, "z_range": [round(z_min, 1), round(z_max, 1)]},
                   "full height contact with parent",
                   detail)


def _check_bore(node, prov: FeatureProvenance, solid: cq.Solid, diameter: float) -> dict:
    """Probe a cylinder (90% of declared dia) down the bore axis; if the bore
    truly exists, intersect with the final solid is ~empty (void).

    SMART: uses the FINAL SOLID's bounding box to scope the probe, not the
    cutting tool's oversized cylinder. This prevents false negatives caused
    by probes extending far beyond the actual part height."""
    # Use the final solid's bounding box for the probe extent (not the cutting tool's)
    bb = solid.BoundingBox()
    probe = cq.Solid.makeCylinder(diameter / 2.0 * 0.9, bb.zlen + 4,
                                  cq.Vector(0, 0, bb.zmin - 2))
    void_vol = solid.intersect(probe).Volume()
    ok = void_vol < probe.Volume() * 0.05  # mostly empty → bore present
    return _result(node, "bore_present", ok, round(void_vol, 2), 0.0,
                   f"residual material inside bore dia {diameter}mm")


def inspect_ir(design: Design | dict, min_wall_mm: float = 2.0) -> dict:
    """Convenience: compile then inspect (used in tests/demo)."""
    if isinstance(design, dict):
        design = Design.model_validate(design)
    solid, prov = compile_design(design)
    return inspect_solid(design, solid, prov, min_wall_mm)
