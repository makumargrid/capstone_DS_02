"""
geometry_ir/validate.py — L1 validation + JSON Schema export.

WHAT: validate_plan(ir) → {valid, errors:[{node, detail}]} in three layers:
        1. Design structure (units, envelope, ≥1 feature),
        2. per-feature params (via primitives.PARAM_MODELS) keyed by feature id,
        3. reference integrity (unique ids; target = a prior feature).
      Patterns validate count + nested leaf feature; `custom` skips param schema.
      export_json_schema() → the versioned contract ForgeCAD validates against.
CALLED BY: pipeline.py (L1 gate), tools/planner_tools.py (planner self-correct),
           handoff/forgecad_emit.py (schema_ref).
CALLS: geometry_ir/models.py (Design), primitives/params.py (PARAM_MODELS).
"""
from __future__ import annotations
import json
from pydantic import ValidationError

from .models import Design, IR_VERSION
from primitives.params import PARAM_MODELS

KNOWN_TYPES = set(PARAM_MODELS) | {"circular_pattern", "linear_pattern", "custom"}


def _fmt(err: dict) -> str:
    loc = ".".join(str(p) for p in err.get("loc", ()))
    return f"{loc}: {err.get('msg', 'invalid')}" if loc else err.get("msg", "invalid")


def validate_plan(ir: dict | Design) -> dict:
    """Validate an IR plan; return {valid, errors:[{node, detail}]} (node-keyed)."""
    errors: list[dict[str, str]] = []

    if isinstance(ir, Design):
        design = ir
    else:
        try:
            design = Design.model_validate(ir)
        except ValidationError as e:
            return {"valid": False,
                    "errors": [{"node": "design", "detail": _fmt(d)} for d in e.errors()]}

    seen: set[str] = set()
    for feat in design.features:
        if feat.id in seen:
            errors.append({"node": feat.id, "detail": "duplicate feature id"})
        seen.add(feat.id)

        if feat.type not in KNOWN_TYPES:
            errors.append({"node": feat.id,
                           "detail": f"unknown type '{feat.type}'. Known: {sorted(KNOWN_TYPES)}"})
        elif feat.type in PARAM_MODELS:
            try:
                PARAM_MODELS[feat.type].model_validate(feat.params)
            except ValidationError as e:
                errors.extend({"node": feat.id, "detail": _fmt(d)} for d in e.errors())
        elif feat.type in ("circular_pattern", "linear_pattern"):
            errors.extend(_validate_pattern(feat.id, feat.params))

        if feat.target is not None and feat.target not in seen:
            errors.append({"node": feat.id,
                           "detail": f"target '{feat.target}' is not a prior feature"})

    return {"valid": not errors, "errors": errors}


def _validate_pattern(node: str, params: dict) -> list[dict[str, str]]:
    """A pattern needs an integer count>=1 and a valid nested leaf `feature`."""
    errs: list[dict[str, str]] = []
    count = params.get("count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        errs.append({"node": node, "detail": "params.count must be an integer >= 1"})
    sub = params.get("feature")
    if not isinstance(sub, dict) or "type" not in sub:
        errs.append({"node": node, "detail": "params.feature must be a nested feature object with a 'type'"})
        return errs
    sub_type = sub["type"]
    if sub_type not in PARAM_MODELS:
        errs.append({"node": node,
                     "detail": f"params.feature.type '{sub_type}' must be a leaf primitive {sorted(PARAM_MODELS)}"})
    else:
        try:
            PARAM_MODELS[sub_type].model_validate(sub.get("params", {}))
        except ValidationError as e:
            errs.extend({"node": node, "detail": f"feature.{_fmt(d)}"} for d in e.errors())
    return errs


def export_json_schema() -> dict:
    """Versioned Draft 2020-12 JSON Schema for a Design (the ForgeCAD contract)."""
    schema = Design.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = f"GeometryIR/{IR_VERSION}"
    schema["x-ir-version"] = IR_VERSION
    return schema


if __name__ == "__main__":
    print(json.dumps(export_json_schema(), indent=2))
