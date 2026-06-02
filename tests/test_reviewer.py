"""Task 6 tests — reviewer deterministic-first routing + surgical repair."""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verification import inspect_ir  # noqa: E402
from agents.reviewer_agent.agent import run_review  # noqa: E402
from tests.fixtures import impeller_ir  # noqa: E402


def test_approves_when_l2_passes():
    l2 = inspect_ir(impeller_ir())
    v = run_review(impeller_ir(), l2)
    assert v["decision"] == "APPROVED"


def test_approves_even_if_vision_disagrees():
    # L2 ground truth passes; vision falsely flags a defect → still APPROVED.
    l2 = inspect_ir(impeller_ir())
    vision = {"suspected_defects": ["blades look merged"], "confidence": "LOW"}
    v = run_review(impeller_ir(), l2, vision_findings=vision)
    assert v["decision"] == "APPROVED"
    assert any("advisory" in d for d in v["discrepancies_found"])


def test_redesign_on_thickness_with_surgical_repair():
    ir = copy.deepcopy(impeller_ir())
    ir["features"][1]["params"]["feature"]["params"]["width"] = 8.6
    l2 = inspect_ir(ir)
    v = run_review(ir, l2)
    assert v["decision"] == "REDESIGN"
    rec = v["recommendations_for_planner"]
    assert "blades" in rec and "2.0" in rec and "count" in rec  # set thickness, keep count


def test_redesign_picks_single_most_blocking():
    # Wrong count AND envelope both fail; reviewer must lead with count.
    ir = copy.deepcopy(impeller_ir())
    ir["features"][1]["params"]["count"] = 3
    l2 = inspect_ir(ir)
    v = run_review(ir, l2)
    assert v["decision"] == "REDESIGN"
    assert "count" in v["recommendations_for_planner"]


def test_halt_when_l2_missing():
    v = run_review(impeller_ir(), {"oops": True})
    assert v["decision"] == "HALT"


def test_verdict_has_no_kernel_internals():
    ir = copy.deepcopy(impeller_ir())
    ir["features"][2]["params"]["diameter"] = 4.0
    v = run_review(ir, inspect_ir(ir))
    blob = str(v).lower()
    assert "topods" not in blob and "occ" not in blob and "cq.solid" not in blob


def test_interface_interference_repair_is_surgical():
    l2 = {"checks": [{"node": "box->lid", "claim": "no_interference", "passed": False,
                      "measured": 8000.0, "expected": "<= 1.0"}]}
    v = run_review({"kind": "assembly"}, l2)
    assert v["decision"] == "REDESIGN"
    assert "box->lid" in v["recommendations_for_planner"] and "overlap" in v["recommendations_for_planner"]


def test_interference_outranks_other_failures():
    l2 = {"checks": [{"node": "a.blades", "claim": "count", "passed": False, "measured": 6, "expected": 7},
                     {"node": "a->b", "claim": "no_interference", "passed": False, "measured": 500, "expected": "<= 1.0"}]}
    v = run_review({"kind": "assembly"}, l2)
    assert "overlap" in v["recommendations_for_planner"]  # interference is top priority


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
