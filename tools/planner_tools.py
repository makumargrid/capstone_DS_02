"""
tools/planner_tools.py — the Planner Agent's function-tools.

USED BY: agents/planner_agent (registered via Agent(tools=[...])). ADK turns each
         function's signature + docstring into the tool schema the model sees, so
         the docstrings here ARE the model-facing contract.
WHEN EACH IS CALLED (by the planner, during a design turn):
  list_primitives()      → first, to discover the vocabulary.
  get_primitive_schema() → next, to get exact param names/types per primitive.
  validate_plan()        → on its draft IR, looping until valid=true (self-correct).
  ask_user()             → only when a critical requirement is genuinely ambiguous.
CALLS: geometry_ir.validate_plan, primitives.list_primitives / params.PARAM_MODELS.
"""
from __future__ import annotations
import sys
import json
import logging
import threading

import math

from geometry_ir import validate_plan as _validate_plan
from primitives import list_primitives as _list_primitives
from primitives.params import PARAM_MODELS
from primitives.registry import LEAF_BUILDERS

logger = logging.getLogger("planner_tools")

# Thread-local cache: stores the last IR that passed validate_plan in this thread.
# extract_ir uses this as a fallback when the model omits the JSON block from its
# final text response after validation succeeds (a known Claude/Gemini behaviour).
_tl = threading.local()


def list_primitives() -> dict:
    """List every primitive type you may use in the Geometry IR.

    Returns {"primitives": [...]} — base solids, patterns, and the `custom`
    escape hatch. Prefer library primitives over `custom`; prefer a pattern
    (circular_pattern/linear_pattern) over hand-placing N identical features.
    """
    return {"primitives": _list_primitives()}


def get_primitive_schema(name: str) -> dict:
    """Get the JSON parameter schema for one primitive type.

    Args:
        name: a primitive type from list_primitives (e.g. 'cylinder', 'cone',
              'box', 'hole', 'tube').
    Returns {"name","schema"}, or {"error"} for patterns/`custom` (structural).
    """
    model = PARAM_MODELS.get(name)
    if model is None:
        return {"error": f"'{name}' has no leaf param schema (pattern/custom are structural)"}
    return {"name": name, "schema": model.model_json_schema()}


def validate_plan(ir_json: str) -> dict:
    """Validate a complete Geometry IR plan BEFORE finalizing it (self-correction).

    Args:
        ir_json: the full IR design as a JSON string.
    Returns {"valid": bool, "errors": [{"node","detail"}, ...]}. Fix the named
    nodes and re-validate until valid=true.
    """
    try:
        ir = json.loads(ir_json)
    except json.JSONDecodeError as e:
        return {"valid": False, "errors": [{"node": "design", "detail": f"invalid JSON: {e}"}]}
    result = _validate_plan(ir)
    if result.get("valid"):
        # Cache so extract_ir can recover the IR if the model omits it from its reply.
        _tl.last_valid_ir = ir
        result["ACTION_REQUIRED"] = (
            "Validation passed. You MUST now write your final response as a SINGLE "
            "```json code block containing the complete IR JSON — the exact same object "
            "you just validated. Do NOT write 'Validation passed' or any prose. "
            "Output ONLY the ```json block. Nothing before it. Nothing after it."
        )
    else:
        _tl.last_valid_ir = None
    return result


def get_last_valid_ir() -> dict | None:
    """Return the last IR that passed validate_plan in this thread, then clear it."""
    ir = getattr(_tl, "last_valid_ir", None)
    _tl.last_valid_ir = None
    return ir


# ask_user is now handled by the Intent Resolution stage (core/intent_resolver.py).
# The planner no longer asks clarification — it receives a confirmed Spec.
# This function is retained for backward compatibility with the question_handler
# plumbing in IRPlanner / IRResolver. It is NOT registered as a planner tool.
def _ask_user_terminal(question: str) -> str:
    """Ask the user one clarifying question (used by Intent Resolution, not planner)."""
    if sys.stdin.isatty():
        print(f"\n🤔 QUESTION: {question}\n>>> ", end="", flush=True)
        return input()
    logger.info(f"Non-interactive; question asked: {question}")
    return ("Running non-interactively — proceed with best engineering judgment "
            "based on the prompt.")


def verify_spatial_placement(feature_type: str, feature_params: dict,
                             parent_type: str, parent_params: dict) -> dict:
    """Check whether a union feature physically protrudes from its parent body.

    Builds BOTH the feature solid and the parent solid using the exact same
    builders the compiler will use, then measures how much of the feature
    extends beyond the parent. Use this BEFORE emitting your IR to verify
    that bosses, ribs, fins, or any union feature will be VISIBLE
    and not embedded inside the parent.

    Args:
        feature_type: the primitive type (e.g. 'box', 'cylinder')
        feature_params: the feature's params dict (at, chord, height, width, etc.)
        parent_type: the parent's type (e.g. 'frustum', 'cone', 'box', 'cylinder')
        parent_params: the parent's params dict (r_base, r_top, height, etc.)

    Returns:
        {protrudes: bool, embedded_ratio: float (0=all new, 1=total embedded),
         feature_max_radius: float, parent_max_radius: float,
         assessment: str (plain-language explanation of findings),
         suggestion: str (what to change if embedded)}
    """
    try:
        import cadquery as cq
    except ImportError:
        return {"error": "CadQuery is not available in this environment"}

    # Build the parent solid
    parent_builder = LEAF_BUILDERS.get(parent_type)
    if parent_builder is None:
        return {"error": f"Unknown parent type '{parent_type}'. Known: {sorted(LEAF_BUILDERS)}"}
    parent_builder_fn, parent_model = parent_builder
    try:
        parent_solid = parent_builder_fn(parent_model.model_validate(parent_params), {})
    except Exception as e:
        return {"error": f"Failed to build parent: {e}"}

    # Build the feature solid
    feat_builder = LEAF_BUILDERS.get(feature_type)
    if feat_builder is None:
        return {"error": f"Unknown feature type '{feature_type}'. Known: {sorted(LEAF_BUILDERS)}"}
    feat_builder_fn, feat_model = feat_builder
    try:
        feat_solid = feat_builder_fn(feat_model.model_validate(feature_params), {})
    except Exception as e:
        return {"error": f"Failed to build feature: {e}"}

    feat_vol = feat_solid.Volume()
    if feat_vol <= 0:
        return {"error": "Feature has zero or negative volume"}

    # Compute embedded ratio
    try:
        embedded_intersection = feat_solid.intersect(parent_solid)
        embedded_vol = embedded_intersection.Volume()
    except Exception:
        embedded_vol = feat_vol  # assume worst case if intersect fails
    embedded_ratio = min(1.0, embedded_vol / feat_vol) if feat_vol > 0 else 1.0
    external_vol = max(0.0, feat_vol - embedded_vol)

    # Compute max radii (for rotationally-symmetric parts)
    feat_bb = feat_solid.BoundingBox()
    parent_bb = parent_solid.BoundingBox()
    feat_max_r = max(
        (v.X ** 2 + v.Y ** 2) ** 0.5 for v in feat_solid.Vertices()
    ) if feat_solid.Vertices() else 0.0
    parent_max_r = max(
        (v.X ** 2 + v.Y ** 2) ** 0.5 for v in parent_solid.Vertices()
    ) if parent_solid.Vertices() else 0.0

    protrudes = embedded_ratio < 0.90
    pct_embedded = embedded_ratio * 100
    pct_protruding = (1 - embedded_ratio) * 100

    if embedded_ratio < 0.05:
        assessment = (
            f"The {feature_type} is well-positioned: {pct_protruding:.0f}% of its "
            f"volume ({external_vol:.0f}mm³ of {feat_vol:.0f}mm³) protrudes beyond "
            f"the {parent_type}. Maximum feature radius {feat_max_r:.1f}mm vs "
            f"parent max radius {parent_max_r:.1f}mm."
        )
        suggestion = "Placement looks good. Proceed with your design."
    elif embedded_ratio < 0.50:
        assessment = (
            f"The {feature_type} partially protrudes: {pct_protruding:.0f}% outside, "
            f"{pct_embedded:.0f}% inside the {parent_type}. Feature max radius "
            f"{feat_max_r:.1f}mm vs parent max radius {parent_max_r:.1f}mm."
        )
        suggestion = (
            f"Consider moving the feature outward (increase at[0]) or increasing "
            f"its radial size (chord/radius) by ~{parent_max_r - feat_max_r:.0f}mm "
            f"so more of it protrudes."
        )
    else:
        assessment = (
            f"WARNING: The {feature_type} is {pct_embedded:.0f}% embedded inside the "
            f"{parent_type} — only {pct_protruding:.0f}% ({external_vol:.0f}mm³ of "
            f"{feat_vol:.0f}mm³) protrudes. Feature max radius {feat_max_r:.1f}mm is "
            f"within parent max radius {parent_max_r:.1f}mm."
        )
        suggestion = (
            f"Move the {feature_type} outward: increase at[0] by at least "
            f"{parent_max_r - feat_max_r:.0f}mm, or increase its radial size. "
            f"For a feature on cone/frustum, position it so it extends outward and verify positioning."
        )

    return {
        "protrudes": protrudes,
        "embedded_ratio": round(embedded_ratio, 4),
        "feature_volume": round(feat_vol, 2),
        "external_volume": round(external_vol, 2),
        "feature_max_radius": round(feat_max_r, 1),
        "parent_max_radius": round(parent_max_r, 1),
        "assessment": assessment,
        "suggestion": suggestion,
    }
