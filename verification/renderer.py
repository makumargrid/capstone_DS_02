"""
verification/renderer.py — L3 multi-view rendering (headless, Docker/terminal identical).

WHAT: render_views(solid, out_dir, prefix) tessellates the compiled solid and
      writes front/side/top/iso/section PNGs via matplotlib `Agg` (no GL/display).
      Feeds the Vision Verifier agent.
CALLED BY: pipeline.py (L3), agents/vision_agent (consumes the PNGs).
CALLS: matplotlib (Agg), numpy, cadquery (solid.tessellate).
"""
from __future__ import annotations
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import cadquery as cq  # noqa: E402

# (elev, azim) camera presets. "section" is handled specially (clip at mid-Z).
_VIEWS = {
    "front": (0, -90),
    "side": (0, 0),
    "top": (90, -90),
    "iso": (30, -60),
    "section": (15, -75),
}


def _mesh(solid: cq.Solid, tol: float = 0.5):
    verts, tris = solid.tessellate(tol)
    V = np.array([[v.x, v.y, v.z] for v in verts])
    T = np.array(tris)
    return V, T


def render_views(solid: cq.Solid, out_dir: str, prefix: str = "09_view") -> dict[str, str]:
    """Render the solid to PNGs (one per view). Returns {view: path}.

    Headless via Agg — produces identical output in Docker and terminal."""
    os.makedirs(out_dir, exist_ok=True)
    V, T = _mesh(solid)
    bb = solid.BoundingBox()
    zmid = (bb.zmin + bb.zmax) / 2.0
    paths: dict[str, str] = {}

    for name, (elev, azim) in _VIEWS.items():
        fig = plt.figure(figsize=(4, 4))
        ax = fig.add_subplot(111, projection="3d")
        Vp, Tp = V, T
        if name == "section":
            # keep triangles whose centroid is below mid-Z → reveal internal voids
            cz = V[T].mean(axis=1)[:, 2]
            Tp = T[cz <= zmid]
        ax.plot_trisurf(Vp[:, 0], Vp[:, 1], Vp[:, 2], triangles=Tp,
                        color="#b8c4d0", edgecolor="#33414f", linewidth=0.05)
        ax.view_init(elev=elev, azim=azim)
        ax.set_box_aspect((bb.xlen or 1, bb.ylen or 1, bb.zlen or 1))
        ax.set_title(name, fontsize=9)
        ax.set_axis_off()
        path = os.path.join(out_dir, f"{prefix}_{name}.png")
        fig.savefig(path, dpi=80, bbox_inches="tight")
        plt.close(fig)
        paths[name] = path
    return paths
