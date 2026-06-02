"""Task 7 tests — end-to-end harness generality (no live LLM).

These exercise the deterministic spine the pipeline runs after the planner:
validate_plan → compile_design → inspect_solid → run_review, on two distinct
object classes (impeller, bracket) with ZERO shape-specific code, plus a render
smoke test. The LLM planner/vision steps are covered separately and are
best-effort in the live pipeline."""
import copy
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geometry_ir import validate_plan
from primitives import compile_design, export_solid  # noqa: E402
from verification import inspect_solid  # noqa: E402
from verification import render_views  # noqa: E402
from agents.reviewer_agent import run_review  # noqa: E402
from tests.fixtures import impeller_ir, bracket_ir  # noqa: E402


def _harness(ir, min_wall=1.0):
    assert validate_plan(ir)["valid"]
    solid, prov = compile_design(ir)
    l2 = inspect_solid(ir, solid, prov, min_wall_mm=min_wall)
    return solid, run_review(ir, l2)


def test_impeller_approved_end_to_end():
    _, v = _harness(impeller_ir())
    assert v["decision"] == "APPROVED", v


def test_bracket_approved_end_to_end_same_code():
    _, v = _harness(bracket_ir())
    assert v["decision"] == "APPROVED", v


def test_bracket_wrong_bolt_count_redesign():
    ir = copy.deepcopy(bracket_ir())
    ir["features"][2]["params"]["count"] = 3
    _, v = _harness(ir)
    assert v["decision"] == "REDESIGN" and "count" in v["recommendations_for_planner"]


def test_both_objects_render_headless():
    for ir in (impeller_ir(), bracket_ir()):
        solid, _ = compile_design(ir)
        with tempfile.TemporaryDirectory() as d:
            paths = render_views(solid, d)
            assert all(os.path.getsize(p) > 0 for p in paths.values())


def test_pipeline_module_imports():
    import pipeline
    assert hasattr(pipeline, "run_pipeline")


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
