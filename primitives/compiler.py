"""
primitives/compiler.py — IR → CadQuery solid (+ per-feature provenance).

WHAT: compile_design(design) walks the validated feature tree, builds each
      feature (leaf via LEAF_BUILDERS, pattern by replication, `custom` via a
      single-scope exec), records provenance (the feature's own solid + bbox/
      volume BEFORE merge), then applies union/cut into the running result.
      This is the GEOMETRY AUTHORITY — a pure function, not an LLM.
CALLED BY: verification/solid_inspector.py, verification/renderer.py (via solid),
           handoff/forgecad_emit.py, pipeline.py.
CALLS: cadquery; geometry_ir/models.py (Design); primitives/registry.py
       (LEAF_BUILDERS); primitives/params.py.

Provenance is what makes intent deterministically checkable in L2 (count pattern
instances, measure each feature) — no mesh clustering.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Any

import cadquery as cq

from geometry_ir.models import Design
from .registry import LEAF_BUILDERS


@dataclass
class FeatureProvenance:
    id: str
    type: str
    op: str
    instances: int                       # 1 for leaves, N for patterns
    bbox: tuple[float, float, float]     # xlen, ylen, zlen of this feature alone
    volume: float
    mesh_only: bool = False
    instance_solids: list = field(default_factory=list)  # cq.Solid per instance


def _bbox_lens(solid: cq.Solid) -> tuple[float, float, float]:
    bb = solid.BoundingBox()
    return (round(bb.xlen, 4), round(bb.ylen, 4), round(bb.zlen, 4))


def _build_leaf(ftype: str, params: dict, ctx: dict) -> cq.Solid:
    builder, model = LEAF_BUILDERS[ftype]
    return builder(model.model_validate(params), ctx)


def _build_pattern(feat, ctx: dict) -> list[cq.Solid]:
    """Replicate a nested feature around an axis (circular) or along a step
    vector (linear). Raises a clear node-keyed error on malformed params."""
    p = feat.params
    sub = p.get("feature")
    if not isinstance(sub, dict) or "type" not in sub:
        raise ValueError(f"feature '{feat.id}': pattern needs a nested 'feature' object")
    count = p.get("count")
    if not isinstance(count, int) or count < 1:
        raise ValueError(f"feature '{feat.id}': pattern needs integer 'count' >= 1")
    base = _build_leaf(sub["type"], sub.get("params", {}), ctx)
    solids = []
    if feat.type == "circular_pattern":
        axis = p.get("axis", [0, 0, 1])
        for i in range(count):
            solids.append(base.rotate((0, 0, 0), (axis[0], axis[1], axis[2]),
                                      360.0 * i / count))
    else:  # linear_pattern
        step = p.get("step", [10, 0, 0])
        for i in range(count):
            solids.append(base.translate((step[0] * i, step[1] * i, step[2] * i)))
    return solids


def _apply(result: cq.Solid | None, solids: list[cq.Solid], op: str) -> cq.Solid:
    for s in solids:
        if result is None:
            result = s
        elif op == "cut":
            result = result.cut(s)
        else:
            result = result.fuse(s)
    return result


def compile_design(design: Design | dict) -> tuple[cq.Solid, list[FeatureProvenance]]:
    """Compile an IR Design into a single cq.Solid + provenance. Raises ValueError
    (keyed to a feature id) on an empty/failed build so the pipeline can route it
    back to the planner."""
    if isinstance(design, dict):
        design = Design.model_validate(design)

    ctx = {"through_len": max(design.envelope.z_mm, 1.0) * 4.0}
    result: cq.Solid | None = None
    provenance: list[FeatureProvenance] = []

    for feat in design.features:
        mesh_only = False
        if feat.type == "custom":
            instances = _run_custom(feat.params)
            mesh_only = True
        elif feat.type in ("circular_pattern", "linear_pattern"):
            instances = _build_pattern(feat, ctx)
        else:
            instances = [_build_leaf(feat.type, feat.params, ctx)]

        if not instances:
            raise ValueError(f"feature '{feat.id}' produced no geometry")

        feat_solid = _apply(None, instances, "union")
        provenance.append(FeatureProvenance(
            id=feat.id, type=feat.type, op=feat.op, instances=len(instances),
            bbox=_bbox_lens(feat_solid), volume=round(feat_solid.Volume(), 4),
            mesh_only=mesh_only, instance_solids=instances))
        result = _apply(result, instances, feat.op)

    if result is None:
        raise ValueError("compilation produced an empty solid")
    return result, provenance


def _run_custom(params: dict) -> list[cq.Solid]:
    """Escape hatch: single-scope exec of a CadQuery snippet that assigns
    `result_solid` (single-scope preserves module-vars-visible-to-functions)."""
    scope: dict[str, Any] = {"cq": cq, "math": math}
    exec(params.get("code", ""), scope)
    rs = scope.get("result_solid")
    if rs is None:
        raise ValueError("custom node did not assign 'result_solid'")
    return [rs.val()] if isinstance(rs, cq.Workplane) else [rs]
