"""Task 2 tests — primitive builders (valid + declared dims) and the compiler."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from primitives import compile_design, export_solid  # noqa: E402
from primitives.builders import (  # noqa: E402
    build_cylinder, build_cone, build_box, build_hole,
)
from primitives.params import (  # noqa: E402
    CylinderParams, ConeParams, BoxParams, HoleParams,
)
from tests.fixtures import impeller_ir  # noqa: E402


def _bb(s):
    b = s.BoundingBox()
    return round(b.xlen, 2), round(b.ylen, 2), round(b.zlen, 2)


# ---- per-primitive builder tests (valid solid + declared dims) ----

def test_cylinder_builder():
    s = build_cylinder(CylinderParams(radius=5, height=10))
    assert s.Volume() > 0 and s.isValid()
    assert _bb(s) == (10.0, 10.0, 10.0)


def test_cone_builder():
    s = build_cone(ConeParams(r_base=5, r_top=2, height=10))
    assert s.isValid() and s.Volume() > 0
    x, y, z = _bb(s)
    assert z == 10.0 and x == 10.0  # widest = base diameter


def test_box_builder_is_base_centered():
    s = build_box(BoxParams(length=2, width=4, height=6))
    assert s.isValid()
    assert _bb(s) == (2.0, 4.0, 6.0)
    b = s.BoundingBox()
    assert abs(b.xmin + 1.0) < 1e-6 and abs(b.zmin) < 1e-6  # centered X, base at z=0


def test_hole_builder_through():
    s = build_hole(HoleParams(diameter=15), ctx={"through_len": 60})
    assert s.isValid()
    x, y, _ = _bb(s)
    assert x == 15.0 and y == 15.0


def test_sphere_builder():
    from primitives.builders import build_sphere
    from primitives.params import SphereParams
    s = build_sphere(SphereParams(radius=10))
    assert s.isValid() and s.Volume() > 0
    assert _bb(s) == (20.0, 20.0, 20.0)


def test_tube_builder_is_hollow():
    from primitives.builders import build_tube
    from primitives.params import TubeParams
    s = build_tube(TubeParams(outer_radius=10, inner_radius=7, height=20))
    assert s.isValid()
    x, y, z = _bb(s)
    assert x == 20.0 and z == 20.0
    # hollow: volume < solid cylinder of same outer radius
    import math
    assert s.Volume() < math.pi * 10**2 * 20


def test_tube_rejects_inner_ge_outer():
    from primitives.params import TubeParams
    import pydantic
    try:
        TubeParams(outer_radius=5, inner_radius=5, height=10)
        assert False, "should reject inner>=outer"
    except pydantic.ValidationError:
        pass


def test_blade_builder_twists():
    from primitives.builders import build_blade
    from primitives.params import BladeParams
    s = build_blade(BladeParams(width=4, chord=12, height=30, twist_deg=40))
    assert s.isValid() and s.Volume() > 0
    assert round(s.BoundingBox().zlen, 1) == 30.0


# ---- compiler tests ----

def test_impeller_compiles_to_single_watertight_solid():
    solid, prov = compile_design(impeller_ir())
    assert solid.isValid()
    assert solid.Volume() > 0
    # single connected solid → one shell
    assert len(solid.Solids()) == 1


def test_provenance_counts():
    _, prov = compile_design(impeller_ir())
    by_id = {p.id: p for p in prov}
    assert by_id["hub"].instances == 1
    assert by_id["blades"].instances == 7
    assert by_id["bore"].instances == 1 and by_id["bore"].op == "cut"


def test_exports_step_and_stl():
    solid, _ = compile_design(impeller_ir())
    with tempfile.TemporaryDirectory() as d:
        step = export_solid(solid, os.path.join(d, "m.step"))
        stl = export_solid(solid, os.path.join(d, "m.stl"))
        assert os.path.getsize(step) > 0 and os.path.getsize(stl) > 0


def test_custom_escape_hatch():
    ir = {
        "version": "1.0", "units": "mm", "process": "FDM",
        "envelope": {"x_mm": 20, "y_mm": 20, "z_mm": 20},
        "features": [{"id": "c", "type": "custom",
                      "params": {"code": "result_solid = cq.Solid.makeBox(10,10,10)"}}],
    }
    solid, prov = compile_design(ir)
    assert solid.isValid() and prov[0].mesh_only is True


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
