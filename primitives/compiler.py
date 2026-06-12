"""
primitives/compiler.py — IR → CadQuery solid (+ per-feature provenance).

WHAT: compile_design(design) walks the validated feature tree, builds each
      feature (leaf via LEAF_BUILDERS, pattern by replication, `custom` via a
      single-scope exec), records provenance (the feature's own solid + bbox/
      volume BEFORE merge), then applies union/cut into the running result.
      This is the GEOMETRY AUTHORITY — a pure function, not an LLM.

SMART COMPILATION:
  1. Topological sort: all unions are processed before all cuts. This prevents
     a common failure where a cut (e.g. bore) is undone by a subsequent union
     (e.g. blades that overlap the bore zone). Works for ANY design.
  2. Feature contribution audit: after building the solid, every union feature
     is measured for how much of its volume actually protrudes from the prior
     solid. Features that are >95% embedded get a diagnostic. This catches
     any embedded feature (blade inside hub, boss inside box, etc.) without
     knowing what the feature IS.

CALLED BY: verification/solid_inspector.py, verification/renderer.py (via solid),
           handoff/forgecad_emit.py, pipeline.py.
CALLS: cadquery; geometry_ir/models.py (Design); primitives/registry.py
       (LEAF_BUILDERS); primitives/params.py.

Provenance is what makes intent deterministically checkable in L2 (count pattern
instances, measure each feature) — no mesh clustering.
"""
from __future__ import annotations
import math
import logging
from dataclasses import dataclass, field
from typing import Any

import cadquery as cq

from geometry_ir.models import Design
from .registry import LEAF_BUILDERS

logger = logging.getLogger("compiler")


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
    # Smart compilation: contribution audit
    external_volume: float = 0.0         # volume added outside the prior solid
    contribution_ratio: float = 1.0      # external_volume / total volume (1.0 = all new)


@dataclass
class CompileDiagnostic:
    """A diagnostic emitted by the compiler when a feature has a geometric issue.
    These are consumed by the pipeline/reviewer to give the planner actionable
    feedback — NOT claim-based, but geometry-derived."""
    feature_id: str
    issue: str        # "embedded", "zero_contribution", "refills_cut"
    detail: str       # human-readable explanation
    suggestion: str   # actionable fix for the planner


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
    """Compile an IR Design into a single cq.Solid + provenance + diagnostics.

    SMART COMPILATION:
      1. Topological sort: unions first, cuts second. This prevents cuts from
         being undone by subsequent unions (e.g. bore refilled by blades).
      2. Feature contribution audit: each union feature is measured for how
         much of its volume protrudes from the prior solid. Embedded features
         get flagged in diagnostics.

    Raises ValueError (keyed to a feature id) on an empty/failed build so the
    pipeline can route it back to the planner."""
    if isinstance(design, dict):
        design = Design.model_validate(design)

    ctx = {"through_len": max(design.envelope.z_mm, 1.0) * 4.0}

    # ── TOPOLOGICAL SORT: unions first, cuts second ─────────────────────
    # Within each group, preserve declaration order so provenance IDs stay stable.
    unions = [f for f in design.features if f.op != "cut"]
    cuts = [f for f in design.features if f.op == "cut"]
    ordered = unions + cuts

    result: cq.Solid | None = None
    provenance: list[FeatureProvenance] = []
    diagnostics: list[CompileDiagnostic] = []

    for feat in ordered:
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
        feat_vol = feat_solid.Volume()

        # ── FEATURE CONTRIBUTION AUDIT (union features only) ────────────
        external_volume = feat_vol
        contribution_ratio = 1.0

        if feat.op == "union" and result is not None and not mesh_only:
            vol_before = result.Volume()
            result_after = _apply(result, instances, feat.op)
            vol_after = result_after.Volume()
            external_volume = max(0.0, vol_after - vol_before)
            contribution_ratio = external_volume / feat_vol if feat_vol > 0 else 0.0

            if contribution_ratio < 0.05:
                diag = CompileDiagnostic(
                    feature_id=feat.id,
                    issue="embedded",
                    detail=(
                        f"Feature '{feat.id}' ({feat.type}) is "
                        f"{(1 - contribution_ratio) * 100:.0f}% inside the existing "
                        f"solid — it contributes only {external_volume:.0f}mm³ of "
                        f"{feat_vol:.0f}mm³ total. The feature's geometry is almost "
                        f"entirely enclosed within the body it targets."
                    ),
                    suggestion=(
                        f"Reposition '{feat.id}' so it extends OUTWARD from the "
                        f"target surface. For features on tapered bodies (cone/frustum), "
                        f"the surface radius shrinks with height — ensure the feature "
                        f"extends beyond the surface at every height. If this is a "
                        f"patterned feature, increase the radial reach (move at[0] "
                        f"outward or increase chord/size) or reduce lean_deg to 0."
                    ),
                )
                diagnostics.append(diag)
                logger.warning(f"[COMPILE] {diag.detail}")

            result = result_after
        else:
            result = _apply(result, instances, feat.op)

        provenance.append(FeatureProvenance(
            id=feat.id, type=feat.type, op=feat.op, instances=len(instances),
            bbox=_bbox_lens(feat_solid), volume=round(feat_vol, 4),
            mesh_only=mesh_only, instance_solids=instances,
            external_volume=round(external_volume, 4),
            contribution_ratio=round(contribution_ratio, 4)))

    if result is None:
        raise ValueError("compilation produced an empty solid")

    # Store diagnostics on the return — accessed via compile_design(...) or
    # via the module-level get_last_diagnostics() for the pipeline.
    _last_diagnostics.clear()
    _last_diagnostics.extend(diagnostics)

    return result, provenance


# Module-level diagnostics buffer (the pipeline reads this after compile_design).
_last_diagnostics: list[CompileDiagnostic] = []


def get_last_diagnostics() -> list[CompileDiagnostic]:
    """Return diagnostics from the most recent compile_design call."""
    return list(_last_diagnostics)


def _run_custom(params: dict) -> list[cq.Solid]:
    """Escape hatch: single-scope exec of a CadQuery snippet that assigns
    `result_solid` (single-scope preserves module-vars-visible-to-functions)."""
    scope: dict[str, Any] = {"cq": cq, "math": math}
    exec(params.get("code", ""), scope)
    rs = scope.get("result_solid")
    if rs is None:
        raise ValueError("custom node did not assign 'result_solid'")
    return [rs.val()] if isinstance(rs, cq.Workplane) else [rs]
