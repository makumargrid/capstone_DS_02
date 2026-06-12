"""Phase 1 tests — intent Spec coverage gate."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.spec import check_coverage, coverage_feedback, _fallback_spec, extract_spec  # noqa: E402

HUB = {"id": "hub", "type": "cone", "params": {"r_base": 50, "r_top": 15, "height": 60}}
BORE = {"id": "bore", "type": "hole", "op": "cut", "target": "hub",
        "params": {"diameter": 15}, "asserts": {"bore_diameter_mm": 15}}


def _pat(item):
    return {"id": "fins", "type": "circular_pattern", "params": {"count": 7, "feature": item}}

BOX = {"id": "f", "type": "box", "params": {"length": 50, "width": 2, "height": 60}}


def test_feature_present_covered():
    ir = {"features": [HUB, _pat(BOX), BORE]}
    spec = [{"id": "r1", "claim": "feature_present", "target": "bore",
             "severity": "required", "description": "bore present"}]
    cov = check_coverage(spec, [], ir)
    assert cov["covered"], cov["missing"]


def test_missing_feature_returns_uncovered():
    ir = {"features": [HUB]}
    spec = [{"id": "r1", "claim": "feature_present", "target": "bore",
             "severity": "required", "description": "bore present"}]
    cov = check_coverage(spec, [], ir)
    assert not cov["covered"]


def test_count_mismatch_is_rejected():
    ir = {"features": [HUB, _pat(BOX), BORE]}
    spec = [{"id": "r1", "claim": "count", "target": "fins", "expected": 7,
             "severity": "required", "description": "7 fins"}]
    cov = check_coverage(spec, [{"node": "fins", "claim": "count", "passed": False,
                                  "measured": 6, "expected": 7}], ir)
    assert not cov["covered"] and any(m["id"] == "r1" for m in cov["missing"])


def test_count_correct_is_covered():
    ir = {"features": [HUB, _pat(BOX), BORE]}
    spec = [{"id": "r1", "claim": "count", "target": "fins", "expected": 7,
             "severity": "required", "description": "7 fins"}]
    cov = check_coverage(spec, [{"node": "fins", "claim": "count", "passed": True,
                                  "measured": 7, "expected": 7}], ir)
    assert cov["covered"]


def test_preferred_severity_never_blocks():
    ir = {"features": [HUB, _pat(BOX), BORE]}
    spec = [{"id": "r2", "claim": "feature_present", "target": "nonexistent",
             "severity": "preferred", "description": "nice to have"}]
    assert check_coverage(spec, [], ir)["covered"]  # preferred → not blocking


def test_fallback_extracts_counts():
    fs = _fallback_spec("bracket with 4 bolt holes and 7 fins")
    counts = {(r["target"], r["expected"]) for r in fs if r["claim"] == "count"}
    assert ("hole", 4) in counts or ("fin", 7) in counts or ("bolt", 4) in counts


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