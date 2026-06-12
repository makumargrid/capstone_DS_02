"""
core/compile_errors.py — translate CadQuery/OCCT errors into actionable feedback.

WHAT: maps raw OCC/CadQuery exception messages to human-readable repair
      instructions that the planner can actually use. Without this mapping,
      the planner receives cryptic C++ exceptions like "BRepAlgoAPI_Fuse:
      Standard_ConstructionError" and cannot diagnose the root cause.

CALLED BY: pipeline.py (when compile_design raises).
CALLS: nothing (pure string mapping).
"""

# Mapping of substrings found in OCCT/CadQuery errors → actionable feedback
_ERROR_MAP: list[tuple[str, str]] = [
    # Boolean operations
    ("Boolean operation failed", (
        "Boolean operation (union/cut) failed: two features are probably not "
        "overlapping enough, or their faces are coincident. Ensure the child "
        "feature extends at least 1-2mm into the parent body. If cutting, make "
        "sure the cut shape fully intersects the target."
    )),
    ("BRepAlgoAPI_Fuse", (
        "Union (fuse) operation failed: features may not overlap, or their "
        "faces are exactly coincident (coplanar). Offset one feature by at "
        "least 0.5mm inside the other so they clearly intersect."
    )),
    ("BRepAlgoAPI_Cut", (
        "Cut (subtract) operation failed: the cutting shape may not intersect "
        "the target body, or its faces are coplanar with the target. Ensure "
        "the hole/cut shape fully passes through the region of the parent body "
        "it should remove, extending at least 1mm beyond each face."
    )),
    ("BRepAlgoAPI_Common", (
        "Intersection operation failed: the two shapes may not overlap at all. "
        "Check that the features share some volume."
    )),

    # Geometry construction
    ("Standard_ConstructionError", (
        "Geometry construction error: a shape could not be built. Common causes: "
        "radius=0 or negative, height=0, a cone/frustum with r_base=r_top=0, "
        "or a loft with incompatible cross-sections. Check all dimensions are "
        "positive and cross-sections have matching vertex counts."
    )),
    ("Standard_NullObject", (
        "A shape reference is null — a feature may be referencing another "
        "feature by `target` that does not exist or failed to compile. Check "
        "that the target feature ID exists and compiled successfully."
    )),
    ("makeCylinder", (
        "Cylinder creation failed: check that radius > 0 and height > 0. "
        "Radius must be positive; height must be positive."
    )),
    ("makeCone", (
        "Cone/frustum creation failed: check r_base > 0, r_top >= 0, "
        "height > 0. At least one radius must be > 0."
    )),
    ("makeLoft", (
        "Loft operation failed: cross-section wires may be incompatible "
        "(different vertex/edge counts) or too close together. Ensure all "
        "cross-sections have the same structure and are spaced apart."
    )),

    # Pattern / transformation issues
    ("rotate", (
        "Rotation/pattern operation failed: the rotation axis may be invalid "
        "or the feature to rotate is too complex. For patterns, check that "
        "`axis` is [x, y, z] with a non-zero vector."
    )),
    ("translate", (
        "Translation/move operation failed: the offset vector may be invalid "
        "or the result lies outside the valid coordinate range."
    )),

    # Export / tessellation
    ("tessellate", (
        "Tessellation failed: the solid geometry may be invalid (non-manifold, "
        "self-intersecting). Check that all boolean operations succeeded and "
        "the final solid is a valid watertight manifold."
    )),
    ("export", (
        "File export failed: the solid may be empty or invalid. Verify that "
        "compilation produced a valid, non-empty solid."
    )),

    # General fallback
    ("", (
        "Compilation produced an error. Common causes: (1) features don't "
        "overlap — ensure child features extend into the parent body by at "
        "least 1mm; (2) invalid dimensions — check all radii, heights, widths "
        "are > 0; (3) pattern axis is [0,0,0] — must be a non-zero vector; "
        "(4) a feature references a `target` that doesn't exist."
    )),
]


def translate_error(raw_error: str) -> str:
    """Map a raw OCCT/CadQuery exception to a human-readable repair instruction.

    Returns a concise, planner-actionable feedback string that can be directly
    sent to the planner for revision. If no specific pattern matches, returns
    the general fallback with the original error appended for context.
    """
    for pattern, feedback in _ERROR_MAP:
        if pattern and pattern in raw_error:
            return feedback
    # Fallback: provide the general guidance plus the raw message
    fallback = _ERROR_MAP[-1][1]
    return f"{fallback}\n\nRaw error (for debugging): {raw_error[:500]}"