"""
geometry_ir/models.py — the IR feature-tree shape (Pydantic v2).

WHAT: Design (units, process, envelope, features), Feature (id, type, params,
      op, target, asserts), Envelope. Holds IR_VERSION. This is the GRAMMAR /
      CONTRACT every stage shares; primitive PARAM schemas live in primitives/.
CALLED BY: geometry_ir/validate.py, primitives/compiler.py, verification/*,
           handoff/forgecad_emit.py, agents/planner_agent.
CALLS: pydantic only (no CadQuery — keeps the contract import-light).
"""
from __future__ import annotations
from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

IR_VERSION = "1.0"


class Envelope(BaseModel):
    """Declared overall bounding box of the finished part (tight, from intent)."""
    model_config = ConfigDict(extra="forbid")
    x_mm: float = Field(gt=0)
    y_mm: float = Field(gt=0)
    z_mm: float = Field(gt=0)
    tolerance_mm: float = Field(default=2.0, ge=0)


class Feature(BaseModel):
    """One node in the feature tree.

    type    — primitive name (resolved against primitives.PARAM_MODELS / registry).
    params  — primitive-specific parameters, validated against the param model.
    op      — how this feature combines with the running solid (union | cut).
    target  — id of a prior feature this op applies onto (None = world/base).
    asserts — optional intent claims the solid inspector (L2) must verify.
    pose    — optional rigid transform {translate: [x,y,z], rotate: [rx,ry,rz]}.
              Applied by the compiler after the builder builds at local origin.
    anchor  — optional relational placement {to, from_face, to_face, align, offset}.
              The compiler resolves this against the referenced feature's geometry
              to produce a pose. Has no effect if used alongside an explicit pose.
              Valid face names for from_face / to_face:
                bottom_center — centre of the bounding-box bottom face (z_min)
                top_center    — centre of the bounding-box top face (z_max)
                center        — volumetric centre of the bounding box
              Unknown face names raise ValueError (loud, not silent fallback).
    """
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    type: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    op: Literal["union", "cut", "fillet", "chamfer"] = "union"
    target: Optional[str] = None
    asserts: Optional[dict[str, Any]] = None
    pose: Optional[dict[str, Any]] = None
    anchor: Optional[dict[str, Any]] = None


class Design(BaseModel):
    """A complete, compilable part specification."""
    model_config = ConfigDict(extra="forbid")
    version: str = IR_VERSION
    units: Literal["mm"] = "mm"
    process: str = "FDM"
    envelope: Envelope
    features: list[Feature] = Field(min_length=1)
