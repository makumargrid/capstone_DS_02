"""Task 5 tests — Planner tools + IR extraction + agent wiring (no live LLM)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.planner_tools import (  # noqa: E402
    list_primitives, get_primitive_schema, validate_plan,
)
from agents.planner_agent.agent import extract_ir, root_agent, IRPlanner  # noqa: E402
from tests.fixtures import pattern_box_ir  # noqa: E402


def test_list_primitives_tool():
    p = list_primitives()["primitives"]
    assert "cylinder" in p and "circular_pattern" in p and "custom" in p


def test_get_primitive_schema_tool():
    s = get_primitive_schema("cone")
    assert s["name"] == "cone" and "properties" in s["schema"]
    assert "r_base" in s["schema"]["properties"]


def test_get_schema_unknown_is_graceful():
    assert "error" in get_primitive_schema("circular_pattern")


def test_validate_plan_tool_accepts_json_string():
    r = validate_plan(json.dumps(pattern_box_ir()))
    assert r["valid"], r["errors"]


def test_validate_plan_tool_reports_node_errors():
    ir = pattern_box_ir()
    del ir["features"][0]["params"]["r_base"]
    r = validate_plan(json.dumps(ir))
    assert not r["valid"]
    assert any(e["node"] == "hub" for e in r["errors"])


def test_validate_plan_tool_bad_json():
    r = validate_plan("{not json")
    assert not r["valid"] and r["errors"][0]["node"] == "design"


def test_extract_ir_from_fenced_block():
    text = "Here is the design.\n```json\n" + json.dumps(pattern_box_ir()) + "\n```\nDone."
    ir = extract_ir(text)
    assert validate_plan(json.dumps(ir))["valid"]


def test_agent_registers_five_tools():
    names = {t.__name__ for t in root_agent.tools}
    assert names == {"list_primitives", "get_primitive_schema", "validate_plan", "verify_spatial_placement", "ask_user"}


def test_planner_drops_ask_user_when_non_interactive():
    p = IRPlanner(interactive=False)
    names = {t.__name__ for t in p.agent.tools}
    assert "ask_user" not in names and "validate_plan" in names


def test_planner_uses_injected_question_handler_when_interactive():
    answers = []

    def handler(question):
        answers.append(question)
        return "use 80 mm"

    p = IRPlanner(interactive=True, question_handler=handler)
    tools = {t.__name__: t for t in p.agent.tools}
    assert "ask_user" in tools
    assert tools["ask_user"]("What diameter?") == "use 80 mm"
    assert answers == ["What diameter?"]


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
