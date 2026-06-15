"""
primitives/builders.py — the geometry store: one builder per primitive type.

WHAT: each `build_*(params, ctx) -> cq.Solid` turns a validated param model into
      a CadQuery solid. Builders are tiny and pure; `hole` reads
      ctx['through_len'] to resolve through-all cuts. THIS is the file to read to
      see exactly how each primitive's geometry is constructed.
CALLED BY: primitives/registry.py (binds them into LEAF_BUILDERS),
           primitives/compiler.py (via LEAF_BUILDERS).
CALLS: cadquery; primitives/params.py (the param models).

INVARIANT: no builder ships without a unit test proving a valid solid at the
           declared dimensions (tests/test_primitives.py).
"""
from __future__ import annotations
import math
import cadquery as cq

from .params import (CylinderParams, ConeParams, BoxParams, HoleParams,
                     SphereParams, TubeParams, ProfileParams)


def _v(at):
    return cq.Vector(at[0], at[1], at[2])


def build_cylinder(p: CylinderParams, ctx=None) -> cq.Solid:
    return cq.Solid.makeCylinder(p.radius, p.height, _v(p.at))


def build_cone(p: ConeParams, ctx=None) -> cq.Solid:
    return cq.Solid.makeCone(p.r_base, p.r_top, p.height, _v(p.at))


def build_box(p: BoxParams, ctx=None) -> cq.Solid:
    """`at` is base-center: centered in X/Y, rising +Z from at.z."""
    pnt = cq.Vector(p.at[0] - p.length / 2.0, p.at[1] - p.width / 2.0, p.at[2])
    return cq.Solid.makeBox(p.length, p.width, p.height, pnt)


def build_hole(p: HoleParams, ctx=None) -> cq.Solid:
    """Cut cylinder. depth=None → through-all via ctx['through_len']; sunk 1mm
    below at.z so a through cut clears the bottom face (no coplanar seam)."""
    ctx = ctx or {}
    margin = 1.0
    length = p.depth if p.depth is not None else ctx.get("through_len", 1000.0)
    base = cq.Vector(p.at[0], p.at[1], p.at[2] - margin)
    return cq.Solid.makeCylinder(p.diameter / 2.0, length + 2 * margin, base)


def build_sphere(p: SphereParams, ctx=None) -> cq.Solid:
    return cq.Solid.makeSphere(p.radius, _v(p.at), angleDegrees1=-90,
                               angleDegrees2=90, angleDegrees3=360)


def build_tube(p: TubeParams, ctx=None) -> cq.Solid:
    """Hollow cylinder: outer minus inner (inner sunk 1mm each end to clear faces)."""
    outer = cq.Solid.makeCylinder(p.outer_radius, p.height, _v(p.at))
    inner = cq.Solid.makeCylinder(p.inner_radius, p.height + 2.0,
                                  cq.Vector(p.at[0], p.at[1], p.at[2] - 1.0))
    return outer.cut(inner)


def build_profile(p: ProfileParams, ctx=None) -> cq.Solid:
    """2D sketch → operation: extrude (along +Z), revolve (around Z), sweep.

    extrude: sketch along +Z for `depth` mm.
    revolve: sketch revolved around Z axis for `revolve_angle` degrees.
    sweep: sketch swept along `sweep_path` waypoints.
    """
    sketch = p.sketch or {}
    stype = sketch.get("type", "circle")
    sp = sketch.get("params", {})

    # Build 2D sketch on XY plane
    wp = cq.Workplane("XY").workplane(offset=p.at[2])
    if stype == "rect":
        w, h = sp.get("width", 10), sp.get("height", 10)
        wp = wp.center(p.at[0], p.at[1]).rect(w, h)
    elif stype == "circle":
        r = sp.get("radius", 5)
        wp = wp.center(p.at[0], p.at[1]).circle(r)
    elif stype == "polygon":
        sides = sp.get("sides", 6)
        r = sp.get("radius", 5)
        wp = wp.center(p.at[0], p.at[1]).polygon(sides, r)
    else:
        raise ValueError(f"Unknown sketch type '{stype}'")

    if p.operation == "extrude":
        result = wp.extrude(p.depth)
    elif p.operation == "revolve":
        # Revolve around Z axis; use revolve_angle if set, else depth (backward compat)
        axis_offset = sketch.get("axis_offset", [0, 0])
        revolve_angle = getattr(p, "revolve_angle", None)
        if revolve_angle is None:
            revolve_angle = float(p.depth)  # backward compat: depth used as angle
        result = wp.revolve(revolve_angle, (axis_offset[0], axis_offset[1], 0),
                            (0, 0, 1))
    elif p.operation == "sweep":
        path = getattr(p, "sweep_path", None) or sketch.get("sweep_path", [])
        if not path or len(path) < 2:
            raise ValueError("sweep requires a sweep_path with at least 2 waypoints")
        # Build a proper Wire path from waypoints using edges
        pts = [cq.Vector(pt[0], pt[1], pt[2]) for pt in path]
        edges = []
        for i in range(len(pts) - 1):
            edges.append(cq.Edge.makeLine(pts[i], pts[i + 1]))
        path_wire = cq.Wire.assembleEdges(edges)
        result = wp.sweep(path_wire)
    else:
        raise ValueError(f"Unknown profile operation '{p.operation}'")

    return result.val() if isinstance(result, cq.Workplane) else result


