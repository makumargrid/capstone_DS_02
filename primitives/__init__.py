"""
primitives/ — the reusable parametric primitive library.

  params.py    typed param schema per primitive (PARAM_MODELS)
  builders.py  the geometry store: one builder per primitive → cq.Solid
  registry.py  LEAF_BUILDERS / FORGECAD_MAP / list_primitives
  compiler.py  IR feature-tree → cq.Solid + provenance (geometry authority)
  export.py    cq.Solid → STEP / STL
"""
from .params import PARAM_MODELS
from .registry import LEAF_BUILDERS, FORGECAD_MAP, list_primitives
from .compiler import compile_design, FeatureProvenance
from .export import export_solid
from .assembly import compile_assembly

__all__ = ["PARAM_MODELS", "LEAF_BUILDERS", "FORGECAD_MAP", "list_primitives",
           "compile_design", "FeatureProvenance", "export_solid", "compile_assembly"]
