"""
primitives/assembly.py — mate solver + multi-body assembly compiler (Phase 2).

WHAT (the robustness idea): the planner DECLARES mates (intent); this module
     SOLVES the placement transform for each component from those mates — the LLM
     never computes assembly math, which is what makes the merge reliable.
  place_components(assembly) -> {id: {design, local, placed, prov}}
       compiles each component (reusing compile_design) and solves its placement.
  compile_assembly(assembly) -> (compound, placed[(id,solid)], bbox)  [bodies kept SEPARATE]
CALLED BY: verification/interface_inspector + assembly_inspector, pipeline, tests.
CALLS: cadquery; primitives/compiler.compile_design; geometry_ir/assembly.

Mate solvers (translation-based; `custom` allows an explicit transform):
  stack_on        : b's bottom face onto a's top face, XY-centered on a.
  concentric      : align b's axis to a's (XY centers); optional z_offset param.
  coincident_face : like stack_on honoring an explicit `gap` param.
  custom          : params['translate']=[x,y,z] (escape hatch).
"""
from __future__ import annotations
import cadquery as cq

from geometry_ir.assembly import Assembly
from .compiler import compile_design


def _solve_mate(a_solid: cq.Solid, b_solid: cq.Solid, mate) -> tuple[float, float, float]:
    """(dx,dy,dz) placing b relative to the already-placed a."""
    A, B = a_solid.BoundingBox(), b_solid.BoundingBox()
    p = mate.params or {}
    if mate.type == "stack_on":
        return (A.center.x - B.center.x, A.center.y - B.center.y, A.zmax - B.zmin)
    if mate.type == "concentric":
        return (A.center.x - B.center.x, A.center.y - B.center.y,
                p.get("z_offset", A.zmin - B.zmin))
    if mate.type == "coincident_face":
        return (A.center.x - B.center.x, A.center.y - B.center.y,
                A.zmax - B.zmin + p.get("gap", 0.0))
    if mate.type == "custom":
        t = p.get("translate", [0, 0, 0])
        return (t[0], t[1], t[2])
    raise ValueError(f"unknown mate type '{mate.type}'")


def place_components(assembly: Assembly | dict) -> dict:
    """Compile + solve placement for every component.
    Returns {id: {'design', 'local' solid, 'placed' solid, 'prov'}}."""
    if isinstance(assembly, dict):
        assembly = Assembly.model_validate(assembly)

    cc: dict = {}
    for c in assembly.components:
        solid, prov = compile_design(c.design)
        cc[c.id] = {"design": c.design.model_dump(), "local": solid, "prov": prov, "placed": None}

    grounded = next(c.id for c in assembly.components if c.grounded)
    cc[grounded]["placed"] = cc[grounded]["local"]

    remaining, progressed = list(assembly.mates), True
    while remaining and progressed:
        progressed = False
        for m in list(remaining):
            if cc[m.a]["placed"] is not None and cc[m.b]["placed"] is None:
                d = _solve_mate(cc[m.a]["placed"], cc[m.b]["local"], m)
                cc[m.b]["placed"] = cc[m.b]["local"].translate(d); remaining.remove(m); progressed = True
            elif cc[m.b]["placed"] is not None and cc[m.a]["placed"] is None:
                d = _solve_mate(cc[m.b]["placed"], cc[m.a]["local"], m)
                cc[m.a]["placed"] = cc[m.a]["local"].translate((-d[0], -d[1], -d[2]))
                remaining.remove(m); progressed = True
    for c in assembly.components:
        if cc[c.id]["placed"] is None:
            cc[c.id]["placed"] = cc[c.id]["local"]
    return cc


def compile_assembly(assembly: Assembly | dict):
    """Returns (compound, placed[(id,solid)], bbox). Bodies kept separate."""
    if isinstance(assembly, dict):
        assembly = Assembly.model_validate(assembly)
    cc = place_components(assembly)
    placed_list = [(c.id, cc[c.id]["placed"]) for c in assembly.components]
    compound = cq.Compound.makeCompound([s for _, s in placed_list])
    return compound, placed_list, compound.BoundingBox()
