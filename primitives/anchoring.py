"""
primitives/anchoring.py — deterministic anchor resolver + pose application.

Given a Feature's anchor or pose, computes the rigid transform and applies
it to a solid built at canonical local origin.

CALLED BY: primitives/compiler.py (during _build_leaf)
CALLS: cadquery
"""
from __future__ import annotations
import math
import cadquery as cq


def apply_pose(solid: cq.Solid, pose: dict) -> cq.Solid:
    """Apply translation + rotation to a solid built at local origin.
    
    pose: {translate: [x, y, z], rotate: [rx, ry, rz]}
    - translate: shift in mm (applied first)
    - rotate: Euler angles in degrees (Z→Y→X, applied after translate)
    """
    result = solid
    if "rotate" in pose:
        rx, ry, rz = [math.radians(a) for a in pose["rotate"]]
        # CadQuery rotate: (axis_start, axis_end, angle_deg)
        if abs(rz) > 1e-9:
            result = result.rotate((0, 0, 0), (0, 0, 1), math.degrees(rz))
        if abs(ry) > 1e-9:
            result = result.rotate((0, 0, 0), (0, 1, 0), math.degrees(ry))
        if abs(rx) > 1e-9:
            result = result.rotate((0, 0, 0), (1, 0, 0), math.degrees(rx))
    if "translate" in pose:
        tx, ty, tz = pose["translate"]
        result = result.translate(cq.Vector(tx, ty, tz))
    return result


def resolve_anchor(anchor: dict, target_solid: cq.Solid,
                   feature_solid: cq.Solid) -> dict:
    """Given an anchor spec and the target/referenced feature's geometry,
    compute the equivalent pose dict {translate, rotate}.

    anchor: {to, from_face, to_face, align, offset}
      - to: target feature id (already resolved by caller)
      - from_face: "bottom_center" | "top_center" | "center"
      - to_face: "bottom_center" | "top_center" | "center"
      - align: "concentric" | "flush" | "centered"
      - offset: [x, y, z] additional shift in mm

    Returns a pose dict ready for apply_pose().
    """
    align = anchor.get("align", "concentric")
    offset = anchor.get("offset", [0, 0, 0])

    # Get the bounding boxes
    target_bb = target_solid.BoundingBox()
    feat_bb = feature_solid.BoundingBox()

    # Compute feature reference point (from_face)
    from_face = anchor.get("from_face", "bottom_center")
    feat_ref = _face_point(feat_bb, from_face)

    # Compute target reference point (to_face)
    to_face = anchor.get("to_face", "top_center")
    target_ref = _face_point(target_bb, to_face)

    # Default translate: align reference points
    tx = target_ref[0] - feat_ref[0] + offset[0]
    ty = target_ref[1] - feat_ref[1] + offset[1]
    tz = target_ref[2] - feat_ref[2] + offset[2]

    # For concentric alignment: override XY to center
    if align == "concentric":
        target_center = target_solid.Center()
        feat_center = feature_solid.Center()
        tx = target_center.x - feat_center.x + offset[0]
        ty = target_center.y - feat_center.y + offset[1]
        # Z: from_face bottom → to_face top
        tz = target_ref[2] - feat_ref[2] + offset[2]
    elif align == "centered":
        target_center = target_solid.Center()
        feat_center = feature_solid.Center()
        tx = target_center.x - feat_center.x + offset[0]
        ty = target_center.y - feat_center.y + offset[1]
        tz = target_center.z - feat_center.z + offset[2]

    return {"translate": [round(tx, 4), round(ty, 4), round(tz, 4)]}


def _face_point(bbox, face_name: str) -> tuple[float, float, float]:
    """Return the anchor point on a bounding box face.

    Valid face names: bottom_center | top_center | center
    Raises ValueError on unknown face names (loud, not silent fallback).
    """
    _VALID_FACE_NAMES = {"bottom_center", "top_center", "center"}
    cx = (bbox.xmin + bbox.xmax) / 2
    cy = (bbox.ymin + bbox.ymax) / 2
    if face_name == "bottom_center":
        return (cx, cy, bbox.zmin)
    elif face_name == "top_center":
        return (cx, cy, bbox.zmax)
    elif face_name == "center":
        return (cx, cy, (bbox.zmin + bbox.zmax) / 2)
    else:
        raise ValueError(
            f"Unknown anchor face name '{face_name}'. "
            f"Valid names: {sorted(_VALID_FACE_NAMES)}"
        )