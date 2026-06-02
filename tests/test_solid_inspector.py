"""Task 3 tests — L2 solid-level deterministic inspector vs IR claims."""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verification import inspect_ir  # noqa: E402
from tests.fixtures import impeller_ir  # noqa: E402


def _fails(ir, node, claim):
    r = inspect_ir(ir)
    return any((not c["passed"]) and c["node"] == node and c["claim"] == claim
               for c in r["checks"])


def test_correct_impeller_passes_all():
    r = inspect_ir(impeller_ir())
    assert r["valid"], r["hard_failures"]


def test_single_solid_and_envelope_present():
    r = inspect_ir(impeller_ir())
    claims = {(c["node"], c["claim"]) for c in r["checks"]}
    assert ("design", "single_solid") in claims
    # impeller is rotational → diameter envelope
    assert ("envelope", "envelope_diameter_mm") in claims


def test_merged_too_thick_blade_caught():
    # The exact legacy miss: 8.6mm blade passing a 'uniform 2mm' spec.
    ir = copy.deepcopy(impeller_ir())
    ir["features"][1]["params"]["feature"]["params"]["width"] = 8.6
    assert _fails(ir, "blades", "uniform_thickness_mm")


def test_too_thin_blade_caught():
    ir = copy.deepcopy(impeller_ir())
    ir["features"][1]["params"]["feature"]["params"]["width"] = 0.6
    assert _fails(ir, "blades", "uniform_thickness_mm")


def test_wrong_blade_count_caught():
    ir = copy.deepcopy(impeller_ir())
    ir["features"][1]["params"]["count"] = 6
    assert _fails(ir, "blades", "count")


def test_missing_bore_caught():
    ir = copy.deepcopy(impeller_ir())
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
    ir = copy.deepcopy(impeller_ir())
    # shrink blade radial reach → circumscribed diameter drops below declared 130
    ir["features"][1]["params"]["feature"]["params"]["at"] = [30.0, 0.0, 0.0]
    r = inspect_ir(ir)
    assert any(c["node"] == "envelope" and not c["passed"] for c in r["checks"])


def test_protruding_feature_passes_coarse_envelope():
    # blades rising ~1mm above the 60mm hub must NOT fail the coarse envelope
    ir = copy.deepcopy(impeller_ir())
    ir["envelope"]["tolerance_mm"] = 1
    ir["features"][1]["params"]["feature"]["params"]["height"] = 61
    zc = [c for c in inspect_ir(ir)["checks"] if c["claim"] == "envelope_z_mm"][0]
    assert zc["passed"], zc


def test_gross_oversize_still_fails_envelope():
    ir = copy.deepcopy(impeller_ir())
    ir["features"][1]["params"]["feature"]["params"]["height"] = 90  # +30mm gross
    zc = [c for c in inspect_ir(ir)["checks"] if c["claim"] == "envelope_z_mm"][0]
    assert not zc["passed"]


def test_twisted_blade_thickness_uses_param():
    # a twisted blade of width=2 must read 2mm (AABB would wrongly read ~21mm)
    ir = copy.deepcopy(impeller_ir())
    ir["features"][1]["params"]["feature"] = {
        "id": "b", "type": "blade",
        "params": {"at": [45, 0, 0], "width": 2, "chord": 40, "height": 60, "twist_deg": 30}}
    tc = [c for c in inspect_ir(ir)["checks"] if c["claim"] == "uniform_thickness_mm"][0]
    assert tc["passed"] and abs(tc["measured"] - 2) < 0.01


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
