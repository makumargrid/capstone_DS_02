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
                     SphereParams, TubeParams, BladeParams)


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


def build_blade(p: BladeParams, ctx=None) -> cq.Solid:
    """Twisted lofted blade with optional radial lean for hub-surface tracking.

    lean_deg=0 (default): vertical blade — identical to original behaviour,
    all existing tests pass unchanged.

    lean_deg>0: each cross-section shifts its center radially inward by
    tan(lean_deg) * (f * height), where f goes 0→1 from base to tip. This
    tracks the surface of a tapered frustum hub and reduces geometric artifacts
    in the blade-hub boolean union.

    Derived formula for a frustum hub:
        lean_deg = degrees(arctan((hub.r_base - hub.r_top) / hub.height))
    """
    n = 8
    lean_tan = math.tan(math.radians(p.lean_deg))
    wires = []
    for k in range(n):
        f = k / (n - 1)
        z = p.at[2] + f * p.height
        # Blade center x: decreases with height when lean_deg > 0 (inward taper)
        cx = p.at[0] - lean_tan * f * p.height
        # Build rect at origin with twist, then move to final (cx, at[1], z)
        w = (cq.Workplane("XY").workplane(offset=z)
             .transformed(rotate=(0, 0, p.twist_deg * f))
             .rect(p.chord, p.width).val())
        w = w.moved(cq.Location(cq.Vector(cx, p.at[1], 0)))
        wires.append(w)
    return cq.Solid.makeLoft(wires, ruled=True)
