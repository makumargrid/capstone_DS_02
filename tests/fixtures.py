
"""Shared IR fixtures for tests. The impeller exercises cone hub, bore, and a
circular pattern of blades — the same part the legacy pipeline failed on.

Blade geometry (intentional): a radial blade is thin TANGENTIALLY (width=Y=2mm
= its "thickness") and extends RADIALLY (length=X) and vertically (height=Z).
The box is placed at X=40 spanning X[20,60], so it embeds 30mm into the hub
(base radius 50) and protrudes to radius 60 → assembly diameter ~120mm."""


def impeller_ir() -> dict:
    return {
        "version": "1.0",
        "units": "mm",
        "process": "FDM",
        "envelope": {"x_mm": 125.0, "y_mm": 125.0, "z_mm": 65.0, "tolerance_mm": 6.5},
        "features": [
            {"id": "hub", "type": "cone",
             "params": {"r_base": 50.0, "r_top": 15.0, "height": 60.0}},
            {"id": "blades", "type": "circular_pattern", "op": "union", "target": "hub",
             "params": {"count": 7, "axis": [0, 0, 1],
                        "feature": {"id": "blade", "type": "blade",
                                    "params": {"at": [45.0, 0.0, 0.0],
                                               "chord": 30.0, "width": 2.0, "height": 60.0,
                                               "twist_deg": -35.0, "lean_deg": 30.0}}},
             "asserts": {"count": 7, "uniform_thickness_mm": 2.0}},
            {"id": "bore", "type": "hole", "op": "cut", "target": "hub",
             "params": {"diameter": 15.0},
             "asserts": {"bore_diameter_mm": 15.0}},
        ],
    }


def bracket_ir() -> dict:
    """A flanged bracket: base plate + vertical riser + 4-bolt circular pattern.
    A deliberately different object class — proves the harness is general (no
    shape-specific code) across impeller and bracket."""
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
