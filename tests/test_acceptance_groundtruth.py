"""
Frozen Ground-Truth Acceptance Oracle — independent regression net.

Each case asserts what is TRUE by construction, with a comment stating WHY.
NEVER weaken or delete an assertion to make it pass — fix the CODE instead.
Adding new cases is encouraged.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verification import inspect_ir
from primitives.compiler import compile_design


# ── Helper: build a dict-based IR, compile + inspect ─────────────────────────
def _check(ir: dict, min_wall_mm=2.0):
    return inspect_ir(ir, min_wall_mm=min_wall_mm)


def _dfm_fail(checks: list, claim: str) -> bool:
    """Return True if a DFM check with `claim` failed."""
    for c in checks:
        if c["claim"] == claim and not c["passed"]:
            return True
    return False


def _dfm_pass(checks: list, claim: str) -> bool:
    """Return True if a DFM check with `claim` passed."""
    for c in checks:
        if c["claim"] == claim and c["passed"]:
            return True
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# CASE 1 — clean_flange
# disc r50 h20, central bore Ø20, 8 holes Ø9 on 80mm bolt circle (r=40,
# spanning r35.5–44.5, inside the r50 rim), FDM.
# TRUE: geometrically valid (no breach, single solid), manufacturable (no DFM
#   violations for this geometry), exactly one solid.
# ═══════════════════════════════════════════════════════════════════════════════
def test_case1_clean_flange():
    ir = {
        "version": "1.0", "units": "mm", "process": "FDM",
        "envelope": {"x_mm": 110, "y_mm": 110, "z_mm": 25, "tolerance_mm": 5},
        "features": [
            {"id": "disc", "type": "cylinder",
             "params": {"radius": 50, "height": 20}},
            {"id": "bore", "type": "hole", "op": "cut", "target": "disc",
             "params": {"diameter": 20}},
            {"id": "bolts", "type": "circular_pattern", "op": "cut", "target": "disc",
             "params": {"count": 8, "axis": [0, 0, 1],
                        "feature": {"id": "h", "type": "hole",
                                    "params": {"at": [40, 0, 0], "diameter": 9}}}},
        ],
    }
    solid, prov = compile_design(ir)
    assert len(solid.Solids()) == 1, "TRUE: single connected solid"

    r = _check(ir)
    # Must expose both flags
    assert r["geometrically_valid"] is True, (
        f"TRUE: holes at r40 (span r35.5–44.5) are inside r50 rim; "
        f"no breach. got hard_failures={r.get('hard_failures', r.get('checks'))}"
    )
    assert r["manufacturable"] is True, (
        f"TRUE: flat-bottom disc on build plate, central bore, 8 bolt holes; "
        f"all within FDM limits. got checks={[c for c in r['checks'] if not c['passed']]}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CASE 2 — rim_breach
# Same disc, 8 holes Ø9 on a 96mm bolt circle (holes at r48, spanning
# r43.5–52.5, breaching the r50 rim).
# TRUE: geometrically_invalid with failing hole_edge_clearance_mm.
#   The holes physically cut through the outer edge.
# ═══════════════════════════════════════════════════════════════════════════════
def test_case2_rim_breach():
    ir = {
        "version": "1.0", "units": "mm", "process": "FDM",
        "envelope": {"x_mm": 110, "y_mm": 110, "z_mm": 15, "tolerance_mm": 5},
        "features": [
            {"id": "disc", "type": "cylinder",
             "params": {"radius": 50, "height": 10}},
            {"id": "holes", "type": "circular_pattern", "op": "cut", "target": "disc",
             "params": {"count": 8, "axis": [0, 0, 1],
                        "feature": {"id": "h", "type": "hole",
                                    "params": {"at": [48, 0, 0], "diameter": 9}}}},
        ],
    }
    r = _check(ir)
    assert r["geometrically_valid"] is False, (
        "TRUE: holes at r48 (span r43.5–52.5) breach the r50 rim"
    )
    # There must be a failing hole_edge_clearance_mm check
    clearance_fails = [c for c in r["checks"]
                       if c["claim"] == "hole_edge_clearance_mm" and not c["passed"]]
    assert len(clearance_fails) > 0, (
        "TRUE: must have a failing hole_edge_clearance_mm check; "
        f"got checks={r['checks']}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CASE 3 — flat_bottom_cylinder
# cylinder r20 h30, FDM (diameter 40 > 30mm bridge limit).
# TRUE: manufacturable=True, no bridge_span failure. The bottom face rests on
#   the build plate; it is SUPPORTED, not an unsupported bridge.
# ═══════════════════════════════════════════════════════════════════════════════
def test_case3_flat_bottom_cylinder():
    ir = {
        "version": "1.0", "units": "mm", "process": "FDM",
        "envelope": {"x_mm": 45, "y_mm": 45, "z_mm": 35, "tolerance_mm": 3},
        "features": [
            {"id": "c", "type": "cylinder", "params": {"radius": 20, "height": 30}},
        ],
    }
    r = _check(ir)
    assert r["manufacturable"] is True, (
        "TRUE: flat-bottom cylinder sits on build plate — no unsupported bridge. "
        f"got checks={[c for c in r['checks'] if not c['passed']]}"
    )
    # bridge_span check must either pass or not exist
    bridge_fails = [c for c in r["checks"]
                    if c["claim"] == "bridge_span" and not c["passed"]]
    assert len(bridge_fails) == 0, (
        f"TRUE: bottom face is build-plate-supported, not a bridge. "
        f"got bridge_fails={bridge_fails}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CASE 4 — overhang_frustum_FDM
# frustum r_base8 r_top30 h15 (≈55° overhang), FDM (max_overhang_deg=45).
# TRUE: geometrically_valid=True, manufacturable=False with failing
#   overhang_angle. The widening wall overhangs at ~55°, beyond 45° limit.
# ═══════════════════════════════════════════════════════════════════════════════
def test_case4_overhang_frustum_fdm():
    ir = {
        "version": "1.0", "units": "mm", "process": "FDM",
        "envelope": {"x_mm": 60, "y_mm": 60, "z_mm": 15, "tolerance_mm": 2},
        "features": [
            {"id": "b", "type": "frustum", "op": "union",
             "params": {"r_base": 8, "r_top": 30, "height": 15}},
        ],
    }
    r = _check(ir)
    assert r["geometrically_valid"] is True, (
        "TRUE: frustum is a valid, single, watertight solid"
    )
    assert r["manufacturable"] is False, (
        "TRUE: ~55° overhang exceeds FDM max_overhang_deg=45"
    )
    assert _dfm_fail(r["checks"], "overhang_angle"), (
        "TRUE: overhang_angle check must fail"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CASE 5 — overhang_frustum_SLS
# Same geometry, process SLS (no overhang limit).
# TRUE: manufacturable=True, no overhang failure. Powder bed needs no supports.
# ═══════════════════════════════════════════════════════════════════════════════
def test_case5_overhang_frustum_sls():
    ir = {
        "version": "1.0", "units": "mm", "process": "SLS",
        "envelope": {"x_mm": 60, "y_mm": 60, "z_mm": 15, "tolerance_mm": 2},
        "features": [
            {"id": "b", "type": "frustum", "op": "union",
             "params": {"r_base": 8, "r_top": 30, "height": 15}},
        ],
    }
    r = _check(ir)
    assert r["manufacturable"] is True, (
        f"TRUE: SLS powder bed supports all overhangs. "
        f"got checks={[c for c in r['checks'] if not c['passed']]}"
    )
    # overhang_angle must either pass or be absent
    overhang_fails = [c for c in r["checks"]
                      if c["claim"] == "overhang_angle" and not c["passed"]]
    assert len(overhang_fails) == 0, (
        f"TRUE: SLS has no overhang limit. got overhang_fails={overhang_fails}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CASE 6 — filleted_box
# box 40×40×20, fillet radius 3, SLS.
# TRUE: geometrically_valid=True, fillet_radius_mm check reports measured radius
#   in [2.0, 4.0] (the realized radius is ~3mm, measured from actual geometry —
#   NOT from volume/bbox which is wrong for this case).
# ═══════════════════════════════════════════════════════════════════════════════
def test_case6_filleted_box():
    ir = {
        "version": "1.0", "units": "mm", "process": "SLS",
        "envelope": {"x_mm": 45, "y_mm": 45, "z_mm": 25, "tolerance_mm": 3},
        "features": [
            {"id": "b", "type": "box", "params": {"length": 40, "width": 40, "height": 20}},
            {"id": "f", "type": "fillet", "op": "fillet", "target": "b",
             "params": {"radius": 3}},
        ],
    }
    r = _check(ir)
    assert r["geometrically_valid"] is True, (
        "TRUE: filleting preserves solid validity"
    )
    fillet_checks = [c for c in r["checks"] if c["claim"] == "fillet_radius_mm"]
    assert len(fillet_checks) > 0, "TRUE: fillet_radius_mm check must exist"
    fc = fillet_checks[0]
    assert fc["passed"], (
        f"TRUE: a 3mm fillet has a 3mm realized radius. "
        f"got measured={fc['measured']}, expected={fc['expected']}"
    )
    # Measured must be numeric (not a string like "no arc radii") and close to 3
    assert isinstance(fc["measured"], (int, float)), (
        f"TRUE: measured must be numeric, got {type(fc['measured'])}: {fc['measured']}"
    )
    assert 2.0 <= fc["measured"] <= 4.0, (
        f"TRUE: realized fillet radius ~3mm. got {fc['measured']}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CASE 7 — anchored_cap
# cone (r_base20 r_top0 h15) anchored concentric on top of cylinder (r20 h30).
# TRUE: geometrically_valid=True, cap contributes >0mm³, solid max-Z ≈ 45.
# Then rebuild with cylinder height 30→45 and assert cap max-Z increased by ~15.
# Relational placement must track the referenced face.
# ═══════════════════════════════════════════════════════════════════════════════
def test_case7_anchored_cap():
    def _build(h):
        ir = {
            "version": "1.0", "units": "mm", "process": "FDM",
            "envelope": {"x_mm": 60, "y_mm": 60, "z_mm": h + 20, "tolerance_mm": 3},
            "features": [
                {"id": "base", "type": "cylinder",
                 "params": {"radius": 20, "height": h}},
                {"id": "cap", "type": "cone", "op": "union", "target": "base",
                 "params": {"r_base": 20, "r_top": 0, "height": 15},
                 "anchor": {"to": "base", "from_face": "bottom_center",
                            "to_face": "top_center", "align": "concentric"}},
            ],
        }
        solid, prov = compile_design(ir)
        r = _check(ir)
        return solid, prov, r

    solid1, _, r1 = _build(30)
    assert r1["geometrically_valid"] is True, (
        "TRUE: anchored cone on cylinder is geometrically valid"
    )
    assert solid1.Volume() > 0, "TRUE: solid has positive volume"
    zmax1 = solid1.BoundingBox().zmax
    assert abs(zmax1 - 45) < 3, (
        f"TRUE: cap bottom at z=30 (cylinder top), cap height=15 → zmax≈45. got {zmax1}"
    )

    # Rebuild with increased cylinder height
    solid2, _, r2 = _build(45)
    zmax2 = solid2.BoundingBox().zmax
    assert abs(zmax2 - 60) < 3, (
        f"TRUE: cylinder height 30→45, cap tracks → zmax≈60. got {zmax2}"
    )
    assert zmax2 - zmax1 > 10, (
        "TRUE: cap z-position tracked the taller cylinder"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CASE 8 — backward_compat
# cylinder r25 h30 + central hole Ø8 via params.at (no pose/anchor).
# TRUE: geometrically_valid=True, single solid. Legacy absolute placement works.
# ═══════════════════════════════════════════════════════════════════════════════
def test_case8_backward_compat():
    ir = {
        "version": "1.0", "units": "mm", "process": "FDM",
        "envelope": {"x_mm": 55, "y_mm": 55, "z_mm": 35, "tolerance_mm": 3},
        "features": [
            {"id": "cyl", "type": "cylinder",
             "params": {"radius": 25, "height": 30}},
            {"id": "h", "type": "hole", "op": "cut", "target": "cyl",
             "params": {"diameter": 8, "at": [0, 0, 0]}},
        ],
    }
    solid, prov = compile_design(ir)
    assert len(solid.Solids()) == 1, "TRUE: single solid"
    r = _check(ir)
    assert r["geometrically_valid"] is True, (
        "TRUE: legacy absolute placement works"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CASE 9 — sandbox_network
# Run a custom-node whose code attempts to reach the network.
# TRUE: the sandbox blocks it; must NOT silently succeed or hang past timeout.
# ═══════════════════════════════════════════════════════════════════════════════
def test_case9_sandbox_network():
    from core.sandbox import run_custom_sandboxed

    code = """
import urllib.request
try:
    urllib.request.urlopen("http://example.com", timeout=2)
    result_solid = None  # should NOT reach here
except Exception:
    # Expected: network blocked
    import cadquery as cq
    result_solid = cq.Workplane("XY").box(10, 10, 5)
"""
    result = run_custom_sandboxed(code)
    # The sandbox must either return success (network was blocked, fallback code ran)
    # or return an error.  It must NOT hang.
    assert "success" in result, f"Sandbox must return a result dict, got {type(result)}"
    # If success=False, the error should be about network blocking or import failure
    # If success=True, the network was blocked and the fallback code ran
    if result["success"]:
        assert result.get("solid") is not None, (
            "TRUE: fallback code produced a solid after network was blocked"
        )
    else:
        assert "error" in result or result.get("error") is not None, (
            "Sandbox should report an error on network access attempt"
        )


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_case")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} oracle cases passed")
    sys.exit(1 if failed else 0)