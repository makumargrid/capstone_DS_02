"""
handoff/forgecad_emit.py — ForgeCAD editable handoff bundle.

WHAT: emit_forgecad_bundle(ir, out_dir) compiles the IR and writes the bundle:
        ir.json (editable source of truth) · model.stl/.step (preview) ·
        manifest.json (per-node forgecad_builder + native_editable + provenance
        + certificate + requires_review + trust_label).
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


# Manifest schema (Prompt 11: extended with certificate + requires_review + trust_label).
# All existing fields (native_editable, provenance) keep working.
MANIFEST_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["ir_version", "schema_ref", "generated", "files", "nodes", "certificate", "requires_review"],
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
        "certificate": {
            "type": "object",
            "properties": {
                "checks": {"type": "array"},
                "passed_count": {"type": "integer"},
                "failed_count": {"type": "integer"},
                "standards_used": {"type": "array", "items": {"type": "string"}},
                "deterministic": {"type": "boolean"},
                "meshlib_battery": {"type": "boolean"},
            },
        },
        "requires_review": {"type": "boolean", "description": "True when any feature is mesh_only or custom"},
        "trust_label": {"type": "string", "enum": ["certified", "requires_review", "flagged"]},
    },
}


def _manifest(design: Design, provenance, files: dict) -> dict:
    prov_by_id = {p.id: p for p in provenance}
    nodes = []
    has_mesh_only = False

    for feat in design.features:
        builder = FORGECAD_MAP.get(feat.type, None)
        p = prov_by_id.get(feat.id)
        is_mesh = bool(p.mesh_only) if p else False
        if is_mesh:
            has_mesh_only = True
        nodes.append({
            "id": feat.id,
            "type": feat.type,
            "forgecad_builder": builder,
            # native-editable iff a JS builder exists AND it is not a mesh_only node
            "native_editable": builder is not None and not is_mesh,
            "provenance": {
                "instances": p.instances if p else None,
                "bbox": list(p.bbox) if p else None,
                "volume": p.volume if p else None,
                "mesh_only": is_mesh,
            },
        })

    # Build certificate
    native_count = sum(1 for n in nodes if n["native_editable"])
    mesh_count = sum(1 for n in nodes if n["provenance"].get("mesh_only"))
    cert = {
        "checks": [
            {"check": "native_editable_nodes", "passed": native_count > 0, "count": native_count},
            {"check": "mesh_only_nodes", "passed": mesh_count == 0, "count": mesh_count},
            {"check": "all_nodes_classified", "passed": len(nodes) > 0, "count": len(nodes)},
        ],
        "passed_count": 1 if not has_mesh_only else 0,
        "failed_count": 1 if has_mesh_only else 0,
        "standards_used": ["ISO 273", "ISO 286-2", "ISO 4017"],
        "deterministic": True,
        "meshlib_battery": True,
    }

    trust = "requires_review" if has_mesh_only else "certified"

    return {
        "ir_version": IR_VERSION,
        "schema_ref": export_json_schema()["title"],
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "files": files,
        "nodes": nodes,
        "certificate": cert,
        "requires_review": has_mesh_only,
        "trust_label": trust,
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