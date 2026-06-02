"""
primitives/export.py — write a compiled cq.Solid to STEP / STL.

WHAT: export_solid(solid, filename) — STL uses fine tessellation (0.01mm chord /
      0.05° angular) for accurate downstream rendering/mesh checks.
CALLED BY: pipeline.py, handoff/forgecad_emit.py.
CALLS: cadquery exporters.
"""
from __future__ import annotations
import cadquery as cq


def export_solid(solid: cq.Solid, filename: str) -> str:
    wp = cq.Workplane(obj=solid) if isinstance(solid, cq.Solid) else solid
    if filename.lower().endswith(".stl"):
        cq.exporters.export(wp, filename, tolerance=0.01, angularTolerance=0.05)
    else:
        cq.exporters.export(wp, filename)
    return filename
