"""
primitives/params.py — typed parameter schema for every primitive (Pydantic v2).

WHAT: one strict model per primitive `type`; PARAM_MODELS maps type→model.
      Decoupled from CadQuery so validation stays import-light.
CALLED BY: geometry_ir/validate.py (L1 param checks), primitives/builders.py
           (each builder takes its model), primitives/registry.py, tools/planner_tools.py.
CALLS: pydantic only.

Convention: `at` = [x,y,z] base-center anchor (default origin). Lengths in mm.
ADD A PRIMITIVE: add its <Name>Params here + an entry in PARAM_MODELS, then a
builder in builders.py and registry entries — and a builder unit test.
"""
from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")
    at: list[float] = Field(default=[0.0, 0.0, 0.0], min_length=3, max_length=3)


class CylinderParams(_Base):
    radius: float = Field(gt=0)
    height: float = Field(gt=0)


class ConeParams(_Base):
    """Truncated cone / frustum. r_top == 0 gives a sharp cone."""
    r_base: float = Field(gt=0)
    r_top: float = Field(ge=0)
    height: float = Field(gt=0)


class BoxParams(_Base):
    """`at` is the base-center; box is centered in X/Y and rises +Z."""
    length: float = Field(gt=0)   # X
    width: float = Field(gt=0)    # Y
    height: float = Field(gt=0)   # Z


class HoleParams(_Base):
    """A cut cylinder. `depth` None = through-all (resolved by compiler)."""
    diameter: float = Field(gt=0)
    depth: Optional[float] = Field(default=None, gt=0)


class SphereParams(_Base):
    """Sphere centered at `at`."""
    radius: float = Field(gt=0)


class ProfileParams(_Base):
    """2D sketch + operation: extrude, revolve, sweep.
    extrude: sketch along +Z for `depth` mm.
    revolve: sketch revolved around Z axis for `revolve_angle` degrees (default 360).
    sweep: sketch swept along `sweep_path` waypoints for total path length.
    """
    operation: str = "extrude"
    depth: float = Field(default=1.0, gt=0)
    sketch: dict[str, Any] = Field(default_factory=dict)
    revolve_angle: float = Field(default=360.0, gt=0, le=360)
    sweep_path: Optional[list[list[float]]] = Field(default=None)
    # sketch types: circle {radius}, rect {width,height}, polygon {sides,radius}


class TubeParams(_Base):
    """Hollow cylinder (pipe): outer/inner radius, height. inner < outer."""
    outer_radius: float = Field(gt=0)
    inner_radius: float = Field(gt=0)
    height: float = Field(gt=0)

    @model_validator(mode="after")
    def _check_radii(self):
        if self.inner_radius >= self.outer_radius:
            raise ValueError("inner_radius must be < outer_radius")
        return self


# type → param model (the validatable primitive vocabulary).
PARAM_MODELS: dict[str, type[BaseModel]] = {
    "cylinder": CylinderParams,
    "cone": ConeParams,
    "frustum": ConeParams,
    "box": BoxParams,
    "hole": HoleParams,
    "sphere": SphereParams,
    "tube": TubeParams,
    "profile": ProfileParams,
}
