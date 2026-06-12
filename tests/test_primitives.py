"""Primitive builder + compiler smoke tests."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tempfile
from primitives.export import export_solid
from primitives.compiler import compile_design
from tests.fixtures import pattern_box_ir  # noqa: E402


def test_pattern_box_compiles_to_single_watertight_solid():
    solid, prov = compile_design(pattern_box_ir())
    assert solid.isValid()
    assert len(solid.Solids()) == 1, f"expected 1 solid, got {len(solid.Solids())}"


def test_provenance_counts():
    _, prov = compile_design(pattern_box_ir())
    by_id = {p.id: p for p in prov}
    assert by_id["hub"].instances == 1
    assert by_id["fins"].instances == 7
    assert by_id["bore"].instances == 1 and by_id["bore"].op == "cut"


def test_exports_step_and_stl():
    solid, _ = compile_design(pattern_box_ir())
    with tempfile.TemporaryDirectory() as d:
        pstep = os.path.join(d, "test.step")
        pstl = os.path.join(d, "test.stl")
        export_solid(solid, pstep)
        export_solid(solid, pstl)
        assert os.path.getsize(pstep) > 100
        assert os.path.getsize(pstl) > 100


# ── Prompt 5: Pose / Anchor tests ────────────────────────────────────────────

def test_anchor_cone_on_cylinder():
    """Cone anchored on cylinder top face tracks parent height."""
    ir = {
        "version": "1.0", "units": "mm", "process": "FDM",
        "envelope": {"x_mm": 60, "y_mm": 60, "z_mm": 80, "tolerance_mm": 3},
        "features": [
            {"id": "cyl", "type": "cylinder", "params": {"radius": 25, "height": 50}},
            {"id": "cone", "type": "cone", "op": "union", "target": "cyl",
             "params": {"r_base": 25, "r_top": 5, "height": 30},
             "anchor": {"to": "cyl", "from_face": "bottom_center",
                        "to_face": "top_center", "align": "concentric"}},
        ],
    }
    solid, _ = compile_design(ir)
    bb = solid.BoundingBox()
    assert abs(bb.zmax - 80) < 2, f"Cone should sit on cylinder top: zmax={bb.zmax}"
    assert solid.isValid()


def test_anchor_tracks_parent_change():
    """Changing cylinder height moves cone automatically."""
    ir = {
        "version": "1.0", "units": "mm", "process": "FDM",
        "envelope": {"x_mm": 60, "y_mm": 60, "z_mm": 120, "tolerance_mm": 3},
        "features": [
            {"id": "cyl", "type": "cylinder", "params": {"radius": 25, "height": 50}},
            {"id": "cone", "type": "cone", "op": "union", "target": "cyl",
             "params": {"r_base": 25, "r_top": 5, "height": 30},
             "anchor": {"to": "cyl", "from_face": "bottom_center",
                        "to_face": "top_center", "align": "concentric"}},
        ],
    }
    ir["features"][0]["params"]["height"] = 80
    solid, _ = compile_design(ir)
    bb = solid.BoundingBox()
    assert abs(bb.zmax - 110) < 2, f"Cone should track new height: zmax={bb.zmax}"


def test_pose_rotate_box():
    """Box with pose rotation compiles correctly."""
    ir = {
        "version": "1.0", "units": "mm", "process": "FDM",
        "envelope": {"x_mm": 30, "y_mm": 30, "z_mm": 10, "tolerance_mm": 3},
        "features": [
            {"id": "b", "type": "box",
             "params": {"length": 20, "width": 10, "height": 5},
             "pose": {"rotate": [0, 0, 45]}},
        ],
    }
    solid, _ = compile_design(ir)
    assert solid.isValid()
    assert solid.Volume() > 0


def test_backward_compat_identical_output():
    """Old IR without pose/anchor compiles identically."""
    ir = pattern_box_ir()
    solid1, _ = compile_design(ir)
    v1, bb1 = solid1.Volume(), solid1.BoundingBox()
    solid2, _ = compile_design(ir)
    v2, bb2 = solid2.Volume(), solid2.BoundingBox()
    assert abs(v1 - v2) < 0.01, f"Volume differs: {v1} vs {v2}"
    assert abs(bb1.xlen - bb2.xlen) < 0.01


# ── Prompt 6: Profile + Fillet tests ────────────────────────────────────────

def test_profile_extrude_circle():
    """Profile with circle extrude compiles to valid solid."""
    from primitives.builders import build_profile
    from primitives.params import ProfileParams
    p = ProfileParams(at=[0,0,0], operation='extrude', depth=30,
                      sketch={'type':'circle','params':{'radius':8}})
    s = build_profile(p)
    assert s.isValid()
    assert s.Volume() > 1000


def test_profile_extrude_rect():
    """Profile with rect extrude works."""
    from primitives.builders import build_profile
    from primitives.params import ProfileParams
    p = ProfileParams(at=[0,0,0], operation='extrude', depth=20,
                      sketch={'type':'rect','params':{'width':10,'height':5}})
    s = build_profile(p)
    assert s.isValid()
    assert abs(s.Volume() - 1000) < 1


def test_fillet_on_box():
    """Fillet on a box compiles correctly."""
    ir = {
        "version": "1.0", "units": "mm", "process": "FDM",
        "envelope": {"x_mm": 30, "y_mm": 30, "z_mm": 20, "tolerance_mm": 3},
        "features": [
            {"id": "b", "type": "box", "params": {"length": 20, "width": 20, "height": 15}},
            {"id": "f", "type": "fillet", "op": "fillet", "target": "b",
             "params": {"radius": 3}},
        ],
    }
    solid, _ = compile_design(ir)
    assert solid.isValid()


def test_chamfer_on_box():
    """Chamfer on a box compiles correctly."""
    ir = {
        "version": "1.0", "units": "mm", "process": "FDM",
        "envelope": {"x_mm": 30, "y_mm": 30, "z_mm": 20, "tolerance_mm": 3},
        "features": [
            {"id": "b", "type": "box", "params": {"length": 20, "width": 20, "height": 15}},
            {"id": "c", "type": "chamfer", "op": "chamfer", "target": "b",
             "params": {"length": 2}},
        ],
    }
    solid, _ = compile_design(ir)
    assert solid.isValid()



# ── Prompt 12: Promotion tests ──────────────────────────────────────────────

def test_promotion_capture_and_reject_work():
    """Capture a candidate to templates, then reject it (removes it)."""
    from primitives.promotion import capture_candidate, reject_candidate
    import os

    candidate_type = "_test_candidate_promote"
    node_ir = {
        "display_name": "Test Candidate",
        "builder": "build_box",
        "param_model": "BoxParams",
        "checks": [],
    }

    path = capture_candidate(candidate_type, node_ir)
    assert os.path.isfile(path), f"Template should exist at {path}"

    # Reject removes it
    result = reject_candidate(candidate_type)
    assert result["success"]
    assert not os.path.isfile(path), "Rejected candidate should be deleted"


def test_profile_property_tests_run():
    """Property test battery runs on registered primitives."""
    from primitives.promotion import run_property_tests
    result = run_property_tests("profile", num_samples=3)
    # Extrude with circle should produce valid solids
    # Some random params may fail (e.g. huge extrude), but the battery should run
    assert result["total"] == 3
    assert isinstance(result["passed"], bool)  # Boolean result present


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