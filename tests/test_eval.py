"""Phase 3 tests — deterministic eval harness + run report (visible outputs)."""
import os, sys, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation.run_eval import run_all, write_scorecard  # noqa: E402
from reporting import build_report  # noqa: E402


def test_every_eval_case_behaves_as_expected():
    results = run_all()
    bad = [r["name"] for r in results if not r["ok"]]
    assert not bad, f"cases not matching expected: {bad}"


def test_eval_includes_edge_cases():
    names = {r["name"] for r in run_all()}
    for must in ("assembly_interference", "assembly_floating", "assembly_cycle",
                 "impeller_flat_blades", "impeller_wrong_count", "blade_too_thick_8mm"):
        assert must in names


def test_scorecard_written():
    with tempfile.TemporaryDirectory() as d:
        path = write_scorecard(run_all(), d)
        assert os.path.getsize(path) > 0
        s = json.load(open(os.path.join(d, "summary.json")))
        assert s["passed"] == s["total"]


def test_run_report_builds_from_artifacts():
    with tempfile.TemporaryDirectory() as d:
        json.dump({"prompt": "x", "process": "FDM"}, open(os.path.join(d, "01_design_brief.json"), "w"))
        json.dump([{"claim": "count", "target": "b", "expected": 7, "severity": "required", "description": "7"}],
                  open(os.path.join(d, "01b_spec.json"), "w"))
        json.dump({"checks": [{"node": "b", "claim": "count", "passed": True, "measured": 7, "expected": 7}]},
                  open(os.path.join(d, "05_outer1_solid_inspection.json"), "w"))
        json.dump({"decision": "APPROVED", "reasoning": "ok"}, open(os.path.join(d, "07_outer1_reviewer_verdict.json"), "w"))
        path = build_report(d)
        assert "APPROVED" in open(path).read()


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
