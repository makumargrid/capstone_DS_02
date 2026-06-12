"""interaction/visual_confirm.py — Visual shape confirmation against reference.

Compares rendered CAD multi-views against a reference image (if available).
This is strictly ADVISORY — images confirm shape/topology only; they never gate
dimensions. Dimensional truth stays in checks/standards.

Returns {shape_match: bool, confidence: "HIGH"|"MEDIUM"|"LOW", notes: str}
"""
from __future__ import annotations
import os


def compare_to_reference(rendered_views: dict[str, str],
                         reference_image: str | None,
                         design_brief: dict | str | None = None) -> dict:
    """Compare rendered CAD views to a reference image.

    Args:
        rendered_views: {view_name: png_path} from renderer.render_views.
        reference_image: path to the reference image, or None.
        design_brief: optional design intent context.

    Returns:
        {shape_match, confidence, notes} — advisory only.
    """
    if reference_image is None:
        return {
            "shape_match": None,
            "confidence": "LOW",
            "notes": "No reference image provided. Shape comparison skipped. "
                     "Please visually inspect the rendered views yourself.",
        }

    if not os.path.isfile(reference_image):
        return {
            "shape_match": None,
            "confidence": "LOW",
            "notes": f"Reference image not found: {reference_image}. "
                     "Please visually inspect the rendered views yourself.",
        }

    # Basic check: rendered views exist
    if not rendered_views:
        return {
            "shape_match": None,
            "confidence": "LOW",
            "notes": "No rendered views available for comparison.",
        }

    # Return an advisory note — the vision agent (L3) performs the actual
    # image comparison. This function provides the plumbing.
    return {
        "shape_match": None,
        "confidence": "MEDIUM",
        "notes": (
            f"Reference image '{os.path.basename(reference_image)}' loaded. "
            f"{len(rendered_views)} rendered view(s) available for visual comparison. "
            "NOTE: Shape comparison is advisory only. Dimensional truth comes from "
            "deterministic checks and standards — images never gate dimensions."
        ),
    }