"""
handoff/forgecad_emit.py — ForgeCAD editable handoff bundle.

WHAT: emit_forgecad_bundle(ir, out_dir) compiles the IR and writes the bundle:
        ir.json (editable source of truth) · model.stl/.step (preview) ·
        manifest.json (per-node forgecad_builder + native_editable + provenance).
      load_and_recompile(dir) is the round-trip (edit params → recompile).
      We OWN this contract: the IR JSON is what crosses the JS/Python boundary.
CALLED BY: pipeline.py (on APPROVED), tests.
CALLS: geometry_ir (Design, validate, schema), primitives (compile_design,
       export_solid, FORGECAD_MAP); jsonschema (manifest validation in tests).
"""
from __future__ import annotations
import os
import json
import shutil
import datetime

from geometry_ir.models import Design, IR_VERSION
from geometry_ir.validate import export_json_schema
from primitives import compile_design, export_solid, FORGECAD_MAP


# Small JSON Schema the manifest must satisfy (validated with jsonschema).
MANIFEST_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["ir_version", "schema_ref", "generated", "files", "nodes"],
    "properties": {
        "ir_version": {"type": "string"},
        "schema_ref": {"type": "string"},
        "generated": {"type": "string"},
        "files": {
            "type": "object",
            "required": ["ir", "stl", "step"],
            "properties": {"ir": {"type": "string"}, "stl": {"type": "string"},
                           "step": {"type": "string"}},
        },
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "type", "forgecad_builder", "native_editable", "provenance"],
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string"},
                    "forgecad_builder": {"type": ["string", "null"]},
                    "native_editable": {"type": "boolean"},
                    "provenance": {"type": "object"},
                },
            },
        },
    },
}


def _manifest(design: Design, provenance, files: dict) -> dict:
    prov_by_id = {p.id: p for p in provenance}
    nodes = []
    for feat in design.features:
        builder = FORGECAD_MAP.get(feat.type, None)
        p = prov_by_id.get(feat.id)
        nodes.append({
            "id": feat.id,
            "type": feat.type,
            "forgecad_builder": builder,
            # native-editable iff a JS builder exists AND it is not a mesh_only node
            "native_editable": builder is not None and not (p and p.mesh_only),
            "provenance": {
                "instances": p.instances if p else None,
                "bbox": list(p.bbox) if p else None,
                "volume": p.volume if p else None,
                "mesh_only": bool(p.mesh_only) if p else False,
            },
        })
    return {
        "ir_version": IR_VERSION,
        "schema_ref": export_json_schema()["title"],
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "files": files,
        "nodes": nodes,
    }


def emit_forgecad_bundle(ir: dict | Design, out_dir: str, basename: str = "model") -> dict:
    """Compile the IR and write the ForgeCAD handoff bundle.

    Returns the manifest dict. Files written: ir.json, <basename>.stl/.step,
    manifest.json (all under out_dir)."""
    design = Design.model_validate(ir) if isinstance(ir, dict) else ir
    os.makedirs(out_dir, exist_ok=True)
    solid, prov = compile_design(design)

    ir_path = os.path.join(out_dir, "ir.json")
    stl_path = os.path.join(out_dir, f"{basename}.stl")
    step_path = os.path.join(out_dir, f"{basename}.step")
    with open(ir_path, "w") as f:
        f.write(design.model_dump_json(indent=2))
    export_solid(solid, stl_path)
    export_solid(solid, step_path)

    # Save immutable originals so the viewer "Reset to original" button can revert.
    # These are written ONCE when the bundle is first created — not overwritten on
    # subsequent recompiles (which only touch ir.json / model.stl).
    orig_ir = os.path.join(out_dir, "ir_original.json")
    orig_stl = os.path.join(out_dir, "model_original.stl")
    if not os.path.exists(orig_ir):
        shutil.copy2(ir_path, orig_ir)
    if not os.path.exists(orig_stl):
        shutil.copy2(stl_path, orig_stl)

    manifest = _manifest(design, prov, {
        "ir": os.path.basename(ir_path),
        "stl": os.path.basename(stl_path),
        "step": os.path.basename(step_path),
    })
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest


def load_and_recompile(bundle_dir: str):
    """Round-trip: load ir.json from a bundle and recompile (edit→recompile).
    Returns (solid, provenance)."""
    with open(os.path.join(bundle_dir, "ir.json")) as f:
        ir = json.load(f)
    return compile_design(ir)
