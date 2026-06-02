"""Task 1 tests — IR schema + validate_plan + JSON Schema export."""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geometry_ir import validate_plan, export_json_schema, Design  # noqa: E402
from tests.fixtures import impeller_ir  # noqa: E402


def test_valid_impeller_passes():
    r = validate_plan(impeller_ir())
    assert r["valid"], r["errors"]


def test_missing_required_param_is_node_keyed():
    ir = impeller_ir()
    del ir["features"][0]["params"]["r_base"]  # cone missing r_base
    r = validate_plan(ir)
    assert not r["valid"]
    assert any(e["node"] == "hub" and "r_base" in e["detail"] for e in r["errors"])


def test_negative_value_rejected():
    ir = impeller_ir()
    ir["features"][0]["params"]["height"] = -5.0
    r = validate_plan(ir)
    assert not r["valid"]
    assert any(e["node"] == "hub" for e in r["errors"])


def test_unknown_type_rejected():
    ir = impeller_ir()
    ir["features"][0]["type"] = "wormhole"
    r = validate_plan(ir)
    assert not r["valid"]
    assert any(e["node"] == "hub" and "unknown type" in e["detail"] for e in r["errors"])


def test_bad_target_reference_rejected():
    ir = impeller_ir()
    ir["features"][2]["target"] = "does_not_exist"  # bore feature
    r = validate_plan(ir)
    assert not r["valid"]
    assert any(e["node"] == "bore" and "target" in e["detail"] for e in r["errors"])


def test_duplicate_id_rejected():
    ir = impeller_ir()
    ir["features"][1]["id"] = "hub"
    r = validate_plan(ir)
    assert not r["valid"]
    assert any("duplicate" in e["detail"] for e in r["errors"])


def test_custom_type_accepted_structurally():
    ir = impeller_ir()
    ir["features"].append({"id": "x", "type": "custom", "params": {"code": "pass"}})
    assert validate_plan(ir)["valid"]


def test_pattern_missing_count_rejected():
    ir = impeller_ir()
    del ir["features"][1]["params"]["count"]  # blades pattern
    r = validate_plan(ir)
    assert not r["valid"]
    assert any(e["node"] == "blades" and "count" in e["detail"] for e in r["errors"])


def test_pattern_bad_nested_param_rejected():
    ir = impeller_ir()
    ir["features"][1]["params"]["feature"]["params"]["width"] = -2
    r = validate_plan(ir)
    assert not r["valid"]
    assert any(e["node"] == "blades" and "feature." in e["detail"] for e in r["errors"])


def test_json_schema_roundtrips():
    schema = export_json_schema()
    assert schema["x-ir-version"] == "1.0"
    json.loads(json.dumps(schema))  # serializable
    # A Design built from the fixture serializes and re-validates.
    d = Design.model_validate(impeller_ir())
    assert validate_plan(json.loads(d.model_dump_json()))["valid"]


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
