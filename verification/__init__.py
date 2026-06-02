"""
verification/ — the quality layers.

  solid_inspector.py  L2 deterministic checks vs IR declared claims (ground truth)
  renderer.py         L3 headless multi-view PNGs for the Vision Verifier
"""
from .solid_inspector import inspect_solid, inspect_ir
from .renderer import render_views

__all__ = ["inspect_solid", "inspect_ir", "render_views"]
