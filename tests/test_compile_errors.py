"""Test core/compile_errors.py — error translation from OCCT exceptions to human feedback."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.compile_errors import translate_error  # noqa: E402


def test_boolean_operation_failed():
    msg = translate_error("Boolean operation failed: BRepAlgoAPI_Fuse")
    assert "overlap" in msg.lower() or "coincident" in msg.lower()


def test_fuse_specific():
    msg = translate_error("BRepAlgoAPI_Fuse: Standard_ConstructionError")
    assert "fuse" in msg.lower() or "union" in msg.lower()


def test_cut_specific():
    msg = translate_error("BRepAlgoAPI_Cut: Standard_ConstructionError")
    assert "cut" in msg.lower() or "subtract" in msg.lower()


def test_standard_construction_error():
    msg = translate_error("Standard_ConstructionError: gp_Dir() - zero norm")
    assert "construction" in msg.lower() or "radius" in msg.lower() or "positive" in msg.lower()


def test_null_object():
    msg = translate_error("Standard_NullObject: BRep_Tool:: no geometry")
    assert "null" in msg.lower() or "reference" in msg.lower() or "target" in msg.lower()


def test_tessellation_error():
    msg = translate_error("BRepMesh_IncrementalMesh::tessellate failed")
    assert "tessellation" in msg.lower() or "manifold" in msg.lower() or "solid" in msg.lower()


def test_export_error():
    msg = translate_error("STEPControl_Writer::export failed")
    assert "export" in msg.lower() or "solid" in msg.lower()


def test_rotation_error():
    msg = translate_error("BRepBuilderAPI_Transform::rotate failed")
    assert "rotation" in msg.lower() or "axis" in msg.lower()


def test_loft_error():
    msg = translate_error("BRepOffsetAPI_ThruSections::makeLoft failed")
    assert "loft" in msg.lower() or "cross-section" in msg.lower()


def test_make_cylinder_error():
    msg = translate_error("BRepPrimAPI_MakeCylinder failed")
    assert "cylinder" in msg.lower() or "radius" in msg.lower()


def test_make_cone_error():
    msg = translate_error("BRepPrimAPI_MakeCone: radius must be positive")
    assert "cone" in msg.lower() or "r_base" in msg.lower() or "radius" in msg.lower()


def test_fallback_for_unknown_error():
    msg = translate_error("Something completely unexpected happened here")
    # Fallback always provides general guidance
    assert "common causes" in msg.lower() or "features" in msg.lower()


def test_translate_error_handles_empty_string():
    msg = translate_error("")
    assert len(msg) > 0  # fallback guidance even for empty input


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