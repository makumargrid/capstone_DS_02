"""
primitives/registry.py — the lookup tables binding the primitive vocabulary.

WHAT:
  LEAF_BUILDERS  type → (builder fn, param model)  [drives the compiler]
  FORGECAD_MAP   type → ForgeCAD JS builder name (None = mesh_only / custom)
  list_primitives() → every type the planner may use (leaves + patterns + custom)

LEAF_BUILDERS and FORGECAD_MAP are built at import time from
config/primitives/*.yaml (metadata) + code builders/param models (logic).
Every YAML must resolve to a real builder and param model — missing or
broken YAMLs crash at import (loud failure, never silent).

CALLED BY: primitives/compiler.py (LEAF_BUILDERS), handoff/forgecad_emit.py
           (FORGECAD_MAP), tools/planner_tools.py (list_primitives).
CALLS: primitives/builders.py, primitives/params.py, core/config_loader.py.

Pattern (circular_/linear_) and `custom` are TREE ops handled by the compiler,
not leaf builders — they are hardcoded in FORGECAD_MAP and list_primitives().
"""
from __future__ import annotations

import primitives.builders as _builders_mod
from .params import PARAM_MODELS
from core.config_loader import load_all_primitive_configs

# ── Build LEAF_BUILDERS and FORGECAD_MAP from config + code ──────────────────

_BUILDER_BY_NAME = {
    name: fn for name, fn in vars(_builders_mod).items()
    if callable(fn) and name.startswith("build_")
}

LEAF_BUILDERS: dict[str, tuple] = {}
FORGECAD_MAP: dict[str, str | None] = {}

for _cfg in load_all_primitive_configs():
    _type = _cfg["type"]
    _builder_name = _cfg["builder"]
    _param_model_name = _cfg["param_model"]
    _forgecad = _cfg.get("forgecad") or None

    # Assert builder exists (Invariant 4: loud on mismatch)
    if _builder_name not in _BUILDER_BY_NAME:
        raise ImportError(
            f"Primitive '{_type}' YAML declares builder '{_builder_name}', "
            f"but no such function exists in primitives/builders.py. "
            f"Available: {sorted(_BUILDER_BY_NAME)}"
        )

    # Assert param model exists (look up by type key, not class name)
    if _type not in PARAM_MODELS:
        raise ImportError(
            f"Primitive '{_type}' YAML has no entry in PARAM_MODELS. "
            f"Available: {sorted(PARAM_MODELS)}"
        )

    LEAF_BUILDERS[_type] = (
        _BUILDER_BY_NAME[_builder_name],
        PARAM_MODELS[_type],
    )
    FORGECAD_MAP[_type] = _forgecad

# ── Hardcoded structural (non-leaf) types ────────────────────────────────────
FORGECAD_MAP.update({
    "circular_pattern": "circularPattern",
    "linear_pattern": "linearPattern",
    "custom": None,  # mesh_only
})


def list_primitives() -> list[str]:
    """All primitive type names the planner may use (leaves + patterns + custom)."""
    return sorted(set(LEAF_BUILDERS) | {"circular_pattern", "linear_pattern", "custom"})