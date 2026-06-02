"""Phase 1 tests — intent Spec coverage gate (the flat-blade-impeller fix)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.spec import check_coverage, coverage_feedback, _fallback_spec, _augment_domain  # noqa: E402

HUB = {"id": "hub", "type": "cone", "params": {"r_base": 50, "r_top": 15, "height": 60}}
BORE = {"id": "bore", "type": "hole", "params": {"diameter": 15}}
def _pat(item):
    return {"id": "blades", "type": "circular_pattern", "params": {"count": 7, "feature": item}}
BOX = {"id": "b", "type": "box", "params": {"length": 50, "width": 2, "height": 60}}
BLADE = {"id": "b", "type": "blade", "params": {"width": 2, "chord": 40, "height": 60, "twist_deg": 30}}

SWEPT_SPEC = [{"id": "r1", "claim": "count", "target": "blades", "expected": 7, "severity": "required", "description": "7 blades"},
              {"id": "r2", "claim": "swept", "target": "blades", "expected": True, "severity": "required", "description": "swept blades"}]
L2_COUNT_OK = [{"node": "blades", "claim": "count", "passed": True, "measured": 7, "expected": 7}]


def test_flat_blade_impeller_is_rejected():
    ir = {"features": [HUB, _pat(BOX), BORE]}
    cov = check_coverage(SWEPT_SPEC, L2_COUNT_OK, ir)
    assert not cov["covered"]
    assert any(m["id"] == "r2" for m in cov["missing"])  # swept uncovered


def test_swept_blade_impeller_is_covered():
    ir = {"features": [HUB, _pat(BLADE), BORE]}
    assert check_coverage(SWEPT_SPEC, L2_COUNT_OK, ir)["covered"]


def test_count_requires_passing_l2():
    ir = {"features": [HUB, _pat(BLADE), BORE]}
    cov = check_coverage(SWEPT_SPEC, [{"node": "blades", "claim": "count", "passed": False, "measured": 6, "expected": 7}], ir)
    assert not cov["covered"] and any(m["id"] == "r1" for m in cov["missing"])


def test_feature_present_and_bore_and_dimension():
    ir = {"features": [HUB, _pat(BLADE), BORE]}
    spec = [
        {"id": "a", "claim": "feature_present", "target": "hub", "severity": "required", "description": "hub"},
        {"id": "b", "claim": "bore_diameter_mm", "target": "bore", "expected": 15, "severity": "required", "description": "bore"},
        {"id": "c", "claim": "dimension", "target": "hub", "param": "base_diameter_mm", "expected": 100, "tolerance": 2, "severity": "required", "description": "base dia 100"},
    ]
    l2 = [{"node": "bore", "claim": "bore_present", "passed": True}]
    cov = check_coverage(spec, l2, ir)
    assert cov["covered"], cov["missing"]


def test_dimension_mismatch_flagged():
    ir = {"features": [HUB]}
    spec = [{"id": "c", "claim": "dimension", "target": "hub", "param": "base_diameter_mm",
             "expected": 130, "tolerance": 2, "severity": "required", "description": "base dia 130"}]
    assert not check_coverage(spec, [], ir)["covered"]  # hub base dia is 100, not 130


def test_preferred_requirement_not_blocking():
    ir = {"features": [HUB, _pat(BOX), BORE]}
    spec = [{"id": "r2", "claim": "swept", "target": "blades", "expected": True,
             "severity": "preferred", "description": "swept (nice to have)"}]
    assert check_coverage(spec, L2_COUNT_OK, ir)["covered"]  # preferred → not blocking


def test_domain_augmentation_adds_swept():
    reqs = _augment_domain("a centrifugal impeller with 7 blades", [
        {"id": "r1", "claim": "count", "target": "blades", "expected": 7}])
    assert any(r["claim"] == "swept" for r in reqs)


def test_fallback_extracts_counts():
    fs = _fallback_spec("impeller with 7 radial blades and 4 bolt holes")
    counts = {(r["target"], r["expected"]) for r in fs if r["claim"] == "count"}
    assert ("blade", 7) in counts and ("hole", 4) in counts


def test_coverage_feedback_mentions_blade_primitive():
    fb = coverage_feedback([{"id": "r2", "description": "swept blades",
                             "why": "'blades' is not a swept blade"}])
    assert "blade" in fb and "twist" in fb


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
