"""Task 8 tests — ForgeCAD handoff bundle + round-trip."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import jsonschema  # noqa: E402
from primitives import compile_design  # noqa: E402
from handoff import emit_forgecad_bundle, load_and_recompile, MANIFEST_SCHEMA  # noqa: E402
from tests.fixtures import pattern_box_ir, bracket_ir  # noqa: E402


def test_bundle_files_written():
    with tempfile.TemporaryDirectory() as d:
        emit_forgecad_bundle(pattern_box_ir(), d)
        for name in ("ir.json", "model.stl", "model.step", "manifest.json"):
            assert os.path.getsize(os.path.join(d, name)) > 0


def test_manifest_validates_against_schema():
    with tempfile.TemporaryDirectory() as d:
        m = emit_forgecad_bundle(bracket_ir(), d)
        jsonschema.validate(m, MANIFEST_SCHEMA)  # raises if invalid


def test_every_node_classified():
    with tempfile.TemporaryDirectory() as d:
        m = emit_forgecad_bundle(pattern_box_ir(), d)
        ids = {n["id"] for n in m["nodes"]}
        assert ids == {"hub", "fins", "bore"}
        for n in m["nodes"]:
            assert n["native_editable"] is True  # all base primitives map natively
            assert n["forgecad_builder"] is not None


def test_custom_node_is_mesh_only():
    ir = {
        "version": "1.0", "units": "mm", "process": "FDM",
        "envelope": {"x_mm": 20, "y_mm": 20, "z_mm": 20},
        "features": [{"id": "c", "type": "custom",
                      "params": {"code": "result_solid = cq.Solid.makeBox(10,10,10)"}}],
    }
    with tempfile.TemporaryDirectory() as d:
        m = emit_forgecad_bundle(ir, d)
        node = m["nodes"][0]
        assert node["native_editable"] is False
        assert node["forgecad_builder"] is None
        assert node["provenance"]["mesh_only"] is True


def test_roundtrip_identical_solid():
    with tempfile.TemporaryDirectory() as d:
        emit_forgecad_bundle(pattern_box_ir(), d)
        original, _ = compile_design(pattern_box_ir())
        reloaded, prov = load_and_recompile(d)
        assert abs(original.Volume() - reloaded.Volume()) < 1e-6
        assert len(original.Solids()) == len(reloaded.Solids())
        bo, br = original.BoundingBox(), reloaded.BoundingBox()
        assert abs(bo.xlen - br.xlen) < 1e-6 and abs(bo.zlen - br.zlen) < 1e-6


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
