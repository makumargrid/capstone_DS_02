"""Shared IR fixtures for tests. A cylinder-hub + circular_pattern of box features
exercises the same verifier code paths: L2 checks, contribution audit, pattern
count, uniform_thickness, bore, and envelope — all with a general box primitive
(no special domain geometry).

Feature geometry: a thin box (width=2mm = its "thickness", length=40mm radial,
height=60mm) placed at X=45 spanning X[25,65], so it embeds 25mm into the hub
(cylinder radius 50) and protrudes to radius 65 → assembly diameter ~130mm.
"""


def pattern_box_ir() -> dict:
    """A general 7-feature patterned part using only box + cylinder + hole primitives."""
    return {
        "version": "1.0",
        "units": "mm",
        "process": "FDM",
        "envelope": {"x_mm": 135.0, "y_mm": 135.0, "z_mm": 65.0, "tolerance_mm": 6.5},
        "features": [
            {"id": "hub", "type": "cylinder",
             "params": {"radius": 50.0, "height": 60.0}},
            {"id": "fins", "type": "circular_pattern", "op": "union", "target": "hub",
             "params": {"count": 7, "axis": [0, 0, 1],
                        "feature": {"id": "fin", "type": "box",
                                    "params": {"at": [45.0, 0.0, 0.0],
                                               "length": 40.0, "width": 2.0, "height": 60.0}}},
             "asserts": {"count": 7, "uniform_thickness_mm": 2.0}},
            {"id": "bore", "type": "hole", "op": "cut", "target": "hub",
             "params": {"diameter": 15.0},
             "asserts": {"bore_diameter_mm": 15.0}},
        ],
    }


def bracket_ir() -> dict:
    """A flanged bracket: base plate + vertical riser + 4-bolt circular pattern.
    A deliberately different object class — proves the harness is general (no
    shape-specific code)."""
    return {
        "version": "1.0", "units": "mm", "process": "CNC",
        "envelope": {"x_mm": 100.0, "y_mm": 100.0, "z_mm": 40.0, "tolerance_mm": 3.0},
        "features": [
            {"id": "base", "type": "box",
             "params": {"at": [0, 0, 0], "length": 100, "width": 100, "height": 10}},
            {"id": "riser", "type": "box", "op": "union", "target": "base",
             "params": {"at": [0, 0, 10], "length": 100, "width": 20, "height": 30}},
            {"id": "bolts", "type": "circular_pattern", "op": "cut", "target": "base",
             "params": {"count": 4, "axis": [0, 0, 1],
                        "feature": {"id": "b", "type": "hole",
                                    "params": {"at": [40, 0, 0], "diameter": 6}}},
             "asserts": {"count": 4}},
        ],
    }


def rim_breach_ir() -> dict:
    """Canonical rim-breach case: 50mm-radius disc with 8 holes Ø9mm on a 48mm
    bolt circle. Hole far edge = 48 + 4.5 = 52.5mm > 50mm outer radius → breach.
    This MUST fail the hole_edge_clearance check."""
    return {
        "version": "1.0",
        "units": "mm",
        "process": "FDM",
        "envelope": {"x_mm": 110.0, "y_mm": 110.0, "z_mm": 15.0, "tolerance_mm": 5.0},
        "features": [
            {"id": "disc", "type": "cylinder",
             "params": {"radius": 50.0, "height": 10.0}},
            {"id": "holes", "type": "circular_pattern", "op": "cut", "target": "disc",
             "params": {"count": 8, "axis": [0, 0, 1],
                        "feature": {"id": "h", "type": "hole",
                                    "params": {"at": [48.0, 0.0, 0.0], "diameter": 9.0}}},
             "asserts": {"count": 8}},
        ],
    }


def rim_safe_ir() -> dict:
    """Safe variant: 50mm-radius disc with 4 holes Ø6mm on a 30mm bolt circle.
    Hole far edge = 30 + 3 = 33mm < 50mm → safe."""
    return {
        "version": "1.0",
        "units": "mm",
        "process": "FDM",
        "envelope": {"x_mm": 110.0, "y_mm": 110.0, "z_mm": 15.0, "tolerance_mm": 5.0},
        "features": [
            {"id": "disc", "type": "cylinder",
             "params": {"radius": 50.0, "height": 10.0}},
            {"id": "holes", "type": "circular_pattern", "op": "cut", "target": "disc",
             "params": {"count": 4, "axis": [0, 0, 1],
                        "feature": {"id": "h", "type": "hole",
                                    "params": {"at": [30.0, 0.0, 0.0], "diameter": 6.0}}},
             "asserts": {"count": 4}},
        ],
    }


def overhang_ir() -> dict:
    """A vertical wall + a 60° sloped cantilever extending outward.
    Uses a rotated box to create a face with a definable overhang angle.
    The arm sits at z=10, length=30, sloping up at 60° from horizontal."""
    return {
        "version": "1.0",
        "units": "mm",
        "process": "FDM",
        "envelope": {"x_mm": 60.0, "y_mm": 60.0, "z_mm": 30.0, "tolerance_mm": 3.0},
        "features": [
            {"id": "wall", "type": "box",
             "params": {"length": 10, "width": 30, "height": 25}},
            {"id": "arm", "type": "box", "op": "union", "target": "wall",
             "params": {"at": [5, 0, 10], "length": 35, "width": 20, "height": 3}},
        ],
    }


def tiny_hole_ir() -> dict:
    """A simple plate with a hole below FDM min_hole=1.5mm."""
    return {
        "version": "1.0",
        "units": "mm",
        "process": "FDM",
        "envelope": {"x_mm": 30.0, "y_mm": 30.0, "z_mm": 5.0, "tolerance_mm": 2.0},
        "features": [
            {"id": "plate", "type": "box",
             "params": {"length": 20, "width": 20, "height": 3}},
            {"id": "small_hole", "type": "hole", "op": "cut", "target": "plate",
             "params": {"at": [5, 0, 0], "diameter": 1.0}},
        ],
    }


def tiny_feature_ir() -> dict:
    """A base with a union feature below FDM min_feature=0.5mm."""
    return {
        "version": "1.0",
        "units": "mm",
        "process": "FDM",
        "envelope": {"x_mm": 30.0, "y_mm": 30.0, "z_mm": 10.0, "tolerance_mm": 2.0},
        "features": [
            {"id": "base", "type": "box",
             "params": {"length": 20, "width": 20, "height": 5}},
            {"id": "nub", "type": "box", "op": "union", "target": "base",
             "params": {"at": [0, 0, 5], "length": 0.3, "width": 0.3, "height": 0.3}},
        ],
    }


# ── FIX 1: Inverted frustum overhang repro ─────────────────────────────────
def inverted_frustum_ir(process="FDM") -> dict:
    """FIX 1 repro: inverted frustum (r_base=8, r_top=30, height=15) on FDM.
    ~55° overhang from vertical — must fail max_overhang_deg=45."""
    return {
        "version": "1.0", "units": "mm", "process": process,
        "envelope": {"x_mm": 60, "y_mm": 60, "z_mm": 15, "tolerance_mm": 2},
        "features": [
            {"id": "b", "type": "frustum", "op": "union",
             "params": {"r_base": 8, "r_top": 30, "height": 15}},
        ],
    }


def vertical_cylinder_ir() -> dict:
    """Vertical-wall cylinder — no overhang, should pass."""
    return {
        "version": "1.0", "units": "mm", "process": "FDM",
        "envelope": {"x_mm": 30, "y_mm": 30, "z_mm": 20, "tolerance_mm": 2},
        "features": [
            {"id": "c", "type": "cylinder", "params": {"radius": 10, "height": 20}},
        ],
    }


def shallow_cone_ir() -> dict:
    """Cone with r_base=30, r_top=15, height=20 — slope ~37° from vertical.
    Should pass FDM max_overhang_deg=45."""
    return {
        "version": "1.0", "units": "mm", "process": "FDM",
        "envelope": {"x_mm": 60, "y_mm": 60, "z_mm": 25, "tolerance_mm": 3},
        "features": [
            {"id": "cone", "type": "cone", "params": {"r_base": 30, "r_top": 15, "height": 20}},
        ],
    }


# ── FIX 2: Anchor placement repro ──────────────────────────────────────────
def anchored_cone_on_cylinder_ir(cylinder_height=30) -> dict:
    """FIX 2 repro: cone anchored via bottom_center→top_center on cylinder."""
    return {
        "version": "1.0", "units": "mm", "process": "FDM",
        "envelope": {"x_mm": 60, "y_mm": 60, "z_mm": cylinder_height + 20, "tolerance_mm": 3},
        "features": [
            {"id": "base", "type": "cylinder",
             "params": {"radius": 20, "height": cylinder_height}},
            {"id": "cap", "type": "cone", "op": "union", "target": "base",
             "params": {"r_base": 20, "r_top": 0, "height": 15},
             "anchor": {"to": "base", "from_face": "bottom_center",
                        "to_face": "top_center", "align": "concentric"}},
        ],
    }


def anchor_bad_vocab_ir() -> dict:
    """FIX 2: anchor with to_face:"top" (bad vocab) — should raise ValueError."""
    return {
        "version": "1.0", "units": "mm", "process": "FDM",
        "envelope": {"x_mm": 40, "y_mm": 40, "z_mm": 45, "tolerance_mm": 2},
        "features": [
            {"id": "base", "type": "cylinder",
             "params": {"radius": 20, "height": 30}},
            {"id": "cap", "type": "cone", "op": "union", "target": "base",
             "params": {"r_base": 20, "r_top": 0, "height": 15},
             "anchor": {"to": "base", "from_face": "bottom_center",
                        "to_face": "top", "align": "concentric"}},
        ],
    }


# ── FIX 5: Fillet/chamfer verification ─────────────────────────────────────
def fillet_box_ir(radius=3.0) -> dict:
    """Box with a fillet at declared radius."""
    return {
        "version": "1.0", "units": "mm", "process": "FDM",
        "envelope": {"x_mm": 30, "y_mm": 30, "z_mm": 20, "tolerance_mm": 3},
        "features": [
            {"id": "b", "type": "box", "params": {"length": 20, "width": 20, "height": 15}},
            {"id": "f", "type": "fillet", "op": "fillet", "target": "b",
             "params": {"radius": radius}},
        ],
    }


def chamfer_box_ir(length=2.0) -> dict:
    """Box with a chamfer at declared length."""
    return {
        "version": "1.0", "units": "mm", "process": "FDM",
        "envelope": {"x_mm": 30, "y_mm": 30, "z_mm": 20, "tolerance_mm": 3},
        "features": [
            {"id": "b", "type": "box", "params": {"length": 20, "width": 20, "height": 15}},
            {"id": "c", "type": "chamfer", "op": "chamfer", "target": "b",
             "params": {"length": length}},
        ],
    }
