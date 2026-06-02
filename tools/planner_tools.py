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

from geometry_ir import validate_plan as _validate_plan
from primitives import list_primitives as _list_primitives
from primitives.params import PARAM_MODELS

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
              'box', 'hole', 'tube', 'blade').
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


def ask_user(question: str) -> str:
    """Ask the user one clarifying question about a genuinely ambiguous, critical
    requirement (key dimension, count, tolerance). Use judgment for minor details.

    Args:
        question: the specific question.
    Returns the user's answer, or a proceed-note when non-interactive.
    """
    if sys.stdin.isatty():
        print(f"\n🤔 PLANNER QUESTION: {question}\n>>> ", end="", flush=True)
        return input()
    logger.info(f"Non-interactive; planner asked: {question}")
    return ("Running non-interactively — proceed with best engineering judgment "
            "based on the prompt.")
