"""
api/recompile.py — the ForgeCAD round-trip core (Phase 5), stateless.

WHAT: recompile_ir(ir) takes an EDITED Geometry IR (part or assembly), runs the
      deterministic spine — validate → compile → inspect — and returns the fresh
      verification checks plus the new STL (base64) for the browser viewer. This
      is the "edit a param → recompile server-side → re-verify" contract made real.
CALLED BY: api/app.py (POST /recompile), invoked by the viewer on every edit.
CALLS: geometry_ir.validate_plan/validate_assembly, primitives.compile_*,
       verification.inspect_solid/inspect_assembly, primitives.export_solid.
Edge cases: invalid edit → {valid:False, stage:'validate', errors}; compile
            failure → {stage:'compile'}; otherwise {valid, checks, stl_b64}.
"""
from __future__ import annotations
import os
import base64
import tempfile

from geometry_ir import validate_plan
from geometry_ir.assembly import validate_assembly
from primitives import compile_design, compile_assembly, export_solid
from verification import inspect_solid
from verification.assembly_inspector import inspect_assembly


def recompile_ir(ir: dict, min_wall_mm: float = 0.5) -> dict:
    """Validate → compile → inspect an edited IR. Returns
    {valid, stage, checks?, errors?, stl_b64?}."""
    is_asm = isinstance(ir, dict) and "components" in ir
    v = validate_assembly(ir) if is_asm else validate_plan(ir)
    if not v["valid"]:
        return {"valid": False, "stage": "validate", "errors": v["errors"]}
    try:
        if is_asm:
            solid, _, _ = compile_assembly(ir)
            checks = inspect_assembly(ir, min_wall_mm=min_wall_mm)["checks"]
        else:
            solid, prov = compile_design(ir)
            checks = inspect_solid(ir, solid, prov, min_wall_mm=min_wall_mm)["checks"]
        with tempfile.TemporaryDirectory() as d:
            p = export_solid(solid, os.path.join(d, "model.stl"))
            stl_b64 = base64.b64encode(open(p, "rb").read()).decode()
    except Exception as e:
        return {"valid": False, "stage": "compile", "errors": [{"node": "compile", "detail": str(e)}]}
    return {"valid": all(c["passed"] for c in checks) if checks else True,
            "stage": "verify", "checks": checks, "stl_b64": stl_b64}
