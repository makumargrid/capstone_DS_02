"""
geometry_ir/ — the IR contract (grammar + L1 validation).

  models.py    Design / Feature / Envelope feature-tree shape + IR_VERSION
  validate.py  validate_plan (node-keyed L1 errors) + export_json_schema
"""
from .models import Design, Feature, Envelope, IR_VERSION
from .validate import validate_plan, export_json_schema, KNOWN_TYPES
from .assembly import Assembly, Component, Mate, validate_assembly

__all__ = ["Design", "Feature", "Envelope", "IR_VERSION",
           "validate_plan", "export_json_schema", "KNOWN_TYPES",
           "Assembly", "Component", "Mate", "validate_assembly"]
