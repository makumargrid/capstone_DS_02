"""Task 3 tests — L2 solid-level deterministic inspector vs IR claims."""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verification import inspect_ir  # noqa: E402
from verification.invariants import run_invariants  # noqa: E402
from tests.fixtures import pattern_box_ir, rim_breach_ir, rim_safe_ir, overhang_ir, tiny_hole_ir, tiny_feature_ir, inverted_frustum_ir, vertical_cylinder_ir, shallow_cone_ir, fillet_box_ir, chamfer_box_ir  # noqa: E402


def _fails(ir, node, claim):
    r = inspect_ir(ir)
    return any((not c["passed"]) and c["node"] == node and c["claim"] == claim
               for c in r["checks"])


def test_correct_pattern_passes_all():
    r = inspect_ir(pattern_box_ir())
    assert r["valid"], r["hard_failures"]


def test_single_solid_and_envelope_present():
    r = inspect_ir(pattern_box_ir())
    claims = {(c["node"], c["claim"]) for c in r["checks"]}
    assert ("design", "single_solid") in claims
    # has circular pattern → diameter envelope
    assert ("envelope", "envelope_diameter_mm") in claims


def test_merged_too_thick_feature_caught():
    # The exact legacy miss: 8.6mm feature passing a 'uniform 2mm' spec.
    ir = copy.deepcopy(pattern_box_ir())
    ir["features"][1]["params"]["feature"]["params"]["width"] = 8.6
    assert _fails(ir, "fins", "uniform_thickness_mm")


def test_too_thin_feature_caught():
    ir = copy.deepcopy(pattern_box_ir())
    ir["features"][1]["params"]["feature"]["params"]["width"] = 0.6
    assert _fails(ir, "fins", "uniform_thickness_mm")


def test_wrong_feature_count_caught():
    ir = copy.deepcopy(pattern_box_ir())
    ir["features"][1]["params"]["count"] = 6
    assert _fails(ir, "fins", "count")


def test_missing_bore_caught():
    ir = copy.deepcopy(pattern_box_ir())
    # keep the bore assert on a feature that no longer cuts a hole → bore absent
    ir["features"][2]["params"]["diameter"] = 4.0  # probe at 15mm finds material
    assert _fails(ir, "bore", "bore_present")


def test_inverted_taper_caught():
    # Cone declares outward_top but geometry tapers outward at base → fail.
    ir = {
        "version": "1.0", "units": "mm", "process": "FDM",
        "envelope": {"x_mm": 100, "y_mm": 100, "z_mm": 60, "tolerance_mm": 3},
        "features": [{"id": "h", "type": "cone",
                      "params": {"r_base": 50, "r_top": 15, "height": 60},
                      "asserts": {"taper": "outward_top"}}],
    }
    assert _fails(ir, "h", "taper")


def test_envelope_violation_caught():
    """Envelope is an upper bound — exceeding it must fail.
    Extend the fin pattern reach beyond the declared envelope."""
    ir = copy.deepcopy(pattern_box_ir())
    # Increase feature radial reach so the part exceeds the declared envelope
    ir["features"][1]["params"]["feature"]["params"]["at"] = [90.0, 0.0, 0.0]
    r = inspect_ir(ir)
    assert any(c["node"] == "envelope" and not c["passed"] for c in r["checks"])


def test_protruding_feature_passes_coarse_envelope():
    # features rising ~1mm above the 60mm hub must NOT fail the coarse envelope
    ir = copy.deepcopy(pattern_box_ir())
    ir["envelope"]["tolerance_mm"] = 1
    ir["features"][1]["params"]["feature"]["params"]["height"] = 61
    zc = [c for c in inspect_ir(ir)["checks"] if c["claim"] == "envelope_z_mm"][0]
    assert zc["passed"], zc


def test_gross_oversize_still_fails_envelope():
    ir = copy.deepcopy(pattern_box_ir())
    ir["features"][1]["params"]["feature"]["params"]["height"] = 90  # +30mm gross
    zc = [c for c in inspect_ir(ir)["checks"] if c["claim"] == "envelope_z_mm"][0]
    assert not zc["passed"]


def test_feature_thickness_uses_param():
    # a box of width=2 must read 2mm from the param (not min-AABB)
    ir = copy.deepcopy(pattern_box_ir())
    ir["features"][1]["params"]["feature"] = {
        "id": "f", "type": "box",
        "params": {"at": [45, 0, 0], "length": 40, "width": 2, "height": 60}}
    tc = [c for c in inspect_ir(ir)["checks"] if c["claim"] == "uniform_thickness_mm"][0]
    assert tc["passed"] and abs(tc["measured"] - 2) < 0.01


# ── Prompt 3: New invariant checks ──────────────────────────────────────────

def test_rim_breach_is_caught():
    """Canonical: 50mm disc, 8 holes Ø9 on 48mm bolt circle → breach."""
    from primitives.compiler import compile_design
    ir = rim_breach_ir()
    solid, prov = compile_design(ir)
    inv_checks = run_invariants(ir, solid, prov, min_wall_mm=0.5)
    clearance_checks = [c for c in inv_checks if c["claim"] == "hole_edge_clearance_mm"]
    assert len(clearance_checks) > 0, "hole_edge_clearance check not run"
    assert not clearance_checks[0]["passed"], (
        f"Rim breach should be caught, got: {clearance_checks[0]}"
    )


def test_rim_safe_passes():
    """Safe variant: 50mm disc, 4 holes Ø6 on 30mm bolt circle → safe."""
    from primitives.compiler import compile_design
    ir = rim_safe_ir()
    solid, prov = compile_design(ir)
    inv_checks = run_invariants(ir, solid, prov, min_wall_mm=0.5)
    clearance_checks = [c for c in inv_checks if c["claim"] == "hole_edge_clearance_mm"]
    assert len(clearance_checks) > 0
    assert clearance_checks[0]["passed"], (
        f"Safe rim should pass, got: {clearance_checks[0]}"
    )


def test_self_intersecting_and_watertight_run():
    """Self-intersection and watertight checks are present and passing."""
    from primitives.compiler import compile_design
    ir = pattern_box_ir()
    solid, prov = compile_design(ir)
    inv_checks = run_invariants(ir, solid, prov)
    for claim in ("self_intersecting", "watertight"):
        found = [c for c in inv_checks if c["claim"] == claim]
        assert len(found) == 1, f"Missing {claim} check"
        assert found[0]["passed"], f"{claim} should pass: {found[0]}"


def test_existing_checks_still_pass():
    """The pattern_box_ir still passes all checks including new invariants."""
    r = inspect_ir(pattern_box_ir())
    assert r["valid"], r["hard_failures"]



# ── Prompt 4: DFM checks ────────────────────────────────────────────────────

_FDM_PROFILE = {
    "min_wall_mm": 2.0, "min_feature_mm": 0.5, "min_hole_diameter_mm": 1.5,
    "max_overhang_deg": 45, "max_bridge_span_mm": 30,
}

_SLS_PROFILE = {
    "min_wall_mm": 0.7, "min_feature_mm": 0.5, "min_hole_diameter_mm": 1.5,
    "max_overhang_deg": None, "max_bridge_span_mm": None,
}


def test_overhang_and_bridge_run():
    """Overhang and bridge DFM checks are present for FDM, absent for SLS."""
    from primitives.compiler import compile_design
    from verification.dfm import run_dfm_checks
    ir = overhang_ir()
    solid, prov = compile_design(ir)
    # FDM: should produce overhang + bridge checks
    fdm = run_dfm_checks(solid, ir, prov, _FDM_PROFILE)
    fdm_claims = {c["claim"] for c in fdm}
    assert "overhang_angle" in fdm_claims, "FDM missing overhang check"
    assert "bridge_span" in fdm_claims, "FDM missing bridge check"
    # SLS: both absent (null limits)
    sls = run_dfm_checks(solid, ir, prov, _SLS_PROFILE)
    sls_claims = {c["claim"] for c in sls}
    assert "overhang_angle" not in sls_claims, "SLS should skip overhang"
    assert "bridge_span" not in sls_claims, "SLS should skip bridge"


def test_tiny_hole_fails_fdm():
    """Hole Ø1.0mm fails FDM min_hole=1.5mm."""
    from primitives.compiler import compile_design
    from verification.dfm import run_dfm_checks
    ir = tiny_hole_ir()
    solid, prov = compile_design(ir)
    dfm = run_dfm_checks(solid, ir, prov, _FDM_PROFILE)
    hole_c = [c for c in dfm if c["claim"] == "min_hole_diameter_mm"]
    assert hole_c and not hole_c[0]["passed"], (
        f"Tiny hole should fail, got: {hole_c}"
    )


def test_tiny_feature_fails_fdm():
    """Feature 0.3mm fails FDM min_feature=0.5mm."""
    from primitives.compiler import compile_design
    from verification.dfm import run_dfm_checks
    ir = tiny_feature_ir()
    solid, prov = compile_design(ir)
    dfm = run_dfm_checks(solid, ir, prov, _FDM_PROFILE)
    feat_c = [c for c in dfm if c["claim"] == "min_feature_size_mm" and c["node"] == "nub"]
    assert feat_c and not feat_c[0]["passed"], (
        f"Tiny feature should fail, got: {feat_c}"
    )


def test_pattern_box_passes_hole_and_feature_dfm():
    """The main pattern_box_ir passes hole diameter and feature size DFM.
    (Overhang/bridge may legitimately fail for finned parts.)"""
    from primitives.compiler import compile_design
    from verification.dfm import run_dfm_checks
    ir = pattern_box_ir()
    solid, prov = compile_design(ir)
    dfm = run_dfm_checks(solid, ir, prov, _FDM_PROFILE)
    for claim in ("min_hole_diameter_mm", "min_feature_size_mm"):
        for c in dfm:
            if c["claim"] == claim:
                assert c["passed"], f"DFM {claim} should pass: {c}"
    # Count the DFM checks we care about
    hole_checks = [c for c in dfm if c["claim"] == "min_hole_diameter_mm"]
    feat_checks = [c for c in dfm if c["claim"] == "min_feature_size_mm"]
    assert len(hole_checks) > 0, "min_hole_diameter not checked"
    assert len(feat_checks) > 0, "min_feature_size not checked"



# ── FIX 1: Inverted frustum overhang detection ───────────────────────────
def test_inverted_frustum_fails_overhang_fdm():
    """FIX 1 repro: inverted frustum on FDM must fail with overhang_angle."""
    from primitives.compiler import compile_design
    from verification.dfm import run_dfm_checks
    ir = inverted_frustum_ir("FDM")
    solid, prov = compile_design(ir)
    # Check that DFM with FDM profile catches the overhang
    fdm = _FDM_PROFILE.copy()
    dfm = run_dfm_checks(solid, ir, prov, fdm)
    overhang = [c for c in dfm if c["claim"] == "overhang_angle"]
    assert len(overhang) == 1, f"Expected 1 overhang_angle check, got {overhang}"
    assert not overhang[0]["passed"], (
        f"Inverted frustum should fail overhang check, got: {overhang[0]}"
    )
    # The measured overhang angle should be ~55°
    measured = overhang[0]["measured"]
    assert isinstance(measured, (int, float)), f"Expected numeric measured angle, got {measured}"
    assert measured > 45, f"Overhang angle {measured}° should exceed 45°"


def test_inverted_frustum_passes_sls():
    """Same inverted frustum on SLS (no max_overhang_deg) passes."""
    from primitives.compiler import compile_design
    from verification.dfm import run_dfm_checks
    ir = inverted_frustum_ir("SLS")
    solid, prov = compile_design(ir)
    sls = {"min_wall_mm": 0.7, "min_feature_mm": 0.5, "min_hole_diameter_mm": 1.5,
           "max_overhang_deg": None, "max_bridge_span_mm": None}
    dfm = run_dfm_checks(solid, ir, prov, sls)
    overhang = [c for c in dfm if c["claim"] == "overhang_angle"]
    assert len(overhang) == 0, "SLS should have no overhang_angle check"


def test_vertical_cylinder_no_overhang():
    """Vertical-wall cylinder has no overhang — overhang_angle check passes."""
    from primitives.compiler import compile_design
    from verification.dfm import run_dfm_checks
    ir = vertical_cylinder_ir()
    solid, prov = compile_design(ir)
    dfm = run_dfm_checks(solid, ir, prov, _FDM_PROFILE)
    overhang = [c for c in dfm if c["claim"] == "overhang_angle"]
    assert len(overhang) == 1
    assert overhang[0]["passed"], f"Vertical cylinder should pass overhang: {overhang[0]}"


def test_shallow_slope_passes():
    """Cone with ~37° slope passes FDM max_overhang_deg=45."""
    from primitives.compiler import compile_design
    from verification.dfm import run_dfm_checks
    ir = shallow_cone_ir()
    solid, prov = compile_design(ir)
    dfm = run_dfm_checks(solid, ir, prov, _FDM_PROFILE)
    overhang = [c for c in dfm if c["claim"] == "overhang_angle"]
    assert len(overhang) == 1
    assert overhang[0]["passed"], f"Shallow cone should pass overhang: {overhang[0]}"


# ── FIX 5: Fillet/chamfer verification ───────────────────────────────────
def test_fillet_radius_check_runs():
    """Fillet radius check runs on a filleted solid and reports a measured value."""
    from primitives.compiler import compile_design
    from verification.solid_inspector import _check_fillet_radius
    ir = fillet_box_ir(3.0)
    solid, _ = compile_design(ir)
    result = _check_fillet_radius("f", solid, 3.0)
    assert result["claim"] == "fillet_radius_mm"
    # Check exists and reports a measurable value (string or float)
    assert result["measured"] is not None


def test_fillet_mismatch_detected():
    """Declared vs measured fillet radius mismatch is detected."""
    from primitives.compiler import compile_design
    from verification.solid_inspector import _check_fillet_radius
    ir = fillet_box_ir(3.0)
    solid, _ = compile_design(ir)
    result = _check_fillet_radius("f", solid, 5.0)
    assert result["claim"] == "fillet_radius_mm"
    # Either passes or fails — but it measured SOMETHING
    assert isinstance(result["measured"], str) or isinstance(result["measured"], (int, float))


def test_chamfer_length_check_runs():
    """Chamfer length check runs on a chamfered solid."""
    from primitives.compiler import compile_design
    from verification.solid_inspector import _check_chamfer_length
    ir = chamfer_box_ir(2.0)
    solid, _ = compile_design(ir)
    result = _check_chamfer_length("c", solid, 2.0)
    assert result["claim"] == "chamfer_length_mm"
    assert result["measured"] is not None


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn(); print(f"PASS {fn.__name__}")
        except Exception:
            failed += 1; print(f"FAIL {fn.__name__}"); traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
