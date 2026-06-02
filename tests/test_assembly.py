"""Phase 2a tests — Assembly IR validation, mate solver, multi-body compile/render."""
import os, sys, tempfile, copy
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geometry_ir.assembly import validate_assembly  # noqa: E402
from primitives.assembly import compile_assembly  # noqa: E402
from verification import render_views  # noqa: E402


def _box(side, h):
    return {"envelope": {"x_mm": side, "y_mm": side, "z_mm": h},
            "features": [{"id": "x", "type": "box",
                          "params": {"length": side, "width": side, "height": h}}]}


def _asm(mate_type="stack_on", params=None):
    return {"components": [{"id": "base", "grounded": True, "design": _box(40, 10)},
                           {"id": "top", "design": _box(40, 5)}],
            "mates": [{"type": mate_type, "a": "base", "b": "top", "params": params or {}}]}


def test_valid_assembly():
    assert validate_assembly(_asm())["valid"]


def test_requires_exactly_one_grounded():
    a = _asm(); a["components"][1]["grounded"] = True
    assert not validate_assembly(a)["valid"]


def test_floating_component_rejected():
    a = _asm(); a["mates"] = []
    assert not validate_assembly(a)["valid"]


def test_cycle_rejected():
    a = _asm()
    a["components"].append({"id": "mid", "design": _box(40, 4)})
    a["mates"] = [{"type": "stack_on", "a": "base", "b": "top"},
                  {"type": "stack_on", "a": "top", "b": "mid"},
                  {"type": "stack_on", "a": "mid", "b": "base"}]  # cycle
    assert not validate_assembly(a)["valid"]


def test_stack_on_places_correctly():
    comp, placed, bb = compile_assembly(_asm())
    assert len(comp.Solids()) == 2
    top = dict(placed)["top"].BoundingBox()
    assert abs(top.zmin - 10) < 1e-6 and abs(top.zmax - 15) < 1e-6


def test_concentric_aligns_axis():
    a = _asm("concentric", {"z_offset": 0})
    # shift the top's local position to prove the solver re-centers it
    a["components"][1]["design"]["features"][0]["params"]["at"] = [20, 0, 0]
    _, placed, _ = compile_assembly(a)
    bb = dict(placed)["top"].BoundingBox()
    assert abs(bb.center.x) < 1e-6 and abs(bb.center.y) < 1e-6  # concentric on axis


def test_custom_transform():
    _, placed, _ = compile_assembly(_asm("custom", {"translate": [5, 0, 30]}))
    bb = dict(placed)["top"].BoundingBox()
    assert abs(bb.zmin - 30) < 1e-6


def test_assembly_renders_headless():
    comp, _, _ = compile_assembly(_asm())
    with tempfile.TemporaryDirectory() as d:
        paths = render_views(comp, d, prefix="asm")
        assert all(os.path.getsize(p) > 0 for p in paths.values())


from primitives.assembly import place_components  # noqa: E402
from verification.interface_inspector import inspect_interfaces  # noqa: E402
from verification.assembly_inspector import inspect_assembly  # noqa: E402
from core.spec import decompose, check_coverage  # noqa: E402


def _placed(a):
    cc = place_components(a)
    return {i: cc[i]["placed"] for i in cc}


def test_interface_good_stack_passes():
    a = _asm()
    assert inspect_interfaces(a, _placed(a))["valid"]


def test_interface_interference_caught():
    a = _asm("custom", {"translate": [0, 0, 2]})  # buries top inside base
    r = inspect_interfaces(a, _placed(a))
    assert not r["valid"] and any("no_interference" in h for h in r["hard_failures"])


def test_interface_floating_caught():
    a = _asm("custom", {"translate": [0, 0, 50]})  # far above → not touching
    r = inspect_interfaces(a, _placed(a))
    assert not r["valid"] and any("contact" in h for h in r["hard_failures"])


def test_inspect_assembly_combines_components_and_interfaces():
    a = _asm()
    r = inspect_assembly(a, min_wall_mm=0.5)
    assert r["valid"]
    nodes = {c["node"].split(".")[0] for c in r["checks"] if "." in c["node"]}
    assert "base" in nodes and "top" in nodes          # per-component L2 ran
    assert any(c["claim"] == "no_interference" for c in r["checks"])  # interface ran


def test_inspect_assembly_flags_interference():
    a = _asm("custom", {"translate": [0, 0, 2]})
    assert not inspect_assembly(a, min_wall_mm=0.5)["valid"]


def test_decompose_guard_requires_two_components():
    # deterministic guard: even if mis-told assembly, <2 components → part
    from core.spec import decompose as _d
    # offline fallback path returns part for a clearly-monolithic prompt
    assert _d("a solid gear with 20 teeth")["mode"] == "part"


def test_assembly_coverage_gate_flattened():
    # spec requires a 'fan' component present; flattened assembly lacks it → uncovered
    asm = {"components": [
        {"id": "base", "design": _box(40, 10)},
        {"id": "top", "design": _box(40, 5)}]}
    flat = {"features": [f for c in asm["components"] for f in c["design"]["features"]]}
    spec = [{"id": "r1", "claim": "feature_present", "target": "fan",
             "severity": "required", "description": "a fan"}]
    assert not check_coverage(spec, [], flat)["covered"]


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
