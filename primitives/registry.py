"""
primitives/registry.py — the lookup tables binding the primitive vocabulary.

WHAT:
  LEAF_BUILDERS  type → (builder fn, param model)  [drives the compiler]
  FORGECAD_MAP   type → ForgeCAD JS builder name (None = mesh_only / custom)
  list_primitives() → every type the planner may use (leaves + patterns + custom)
CALLED BY: primitives/compiler.py (LEAF_BUILDERS), handoff/forgecad_emit.py
           (FORGECAD_MAP), tools/planner_tools.py (list_primitives).
CALLS: primitives/builders.py, primitives/params.py.

Pattern (circular_/linear_) and `custom` are TREE ops handled by the compiler,
not leaf builders — they appear only in FORGECAD_MAP and list_primitives().
"""
from __future__ import annotations
from .params import (CylinderParams, ConeParams, BoxParams, HoleParams,
                     SphereParams, TubeParams, BladeParams)
from .builders import (build_cylinder, build_cone, build_box, build_hole,
                       build_sphere, build_tube, build_blade)

LEAF_BUILDERS = {
    "cylinder": (build_cylinder, CylinderParams),
    "cone": (build_cone, ConeParams),
    "frustum": (build_cone, ConeParams),
    "box": (build_box, BoxParams),
    "hole": (build_hole, HoleParams),
    "sphere": (build_sphere, SphereParams),
    "tube": (build_tube, TubeParams),
    "blade": (build_blade, BladeParams),
}

FORGECAD_MAP = {
    "cylinder": "cylinder", "cone": "cone", "frustum": "cone", "box": "box",
    "hole": "hole", "sphere": "sphere", "tube": "tube", "blade": "blade",
    "circular_pattern": "circularPattern", "linear_pattern": "linearPattern",
    "custom": None,  # mesh_only
}


def list_primitives() -> list[str]:
    """All primitive type names the planner may use (leaves + patterns + custom)."""
    return sorted(set(LEAF_BUILDERS) | {"circular_pattern", "linear_pattern", "custom"})
