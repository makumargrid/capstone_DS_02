"""
evaluation/cases.py — the deterministic edge-case library.

WHAT: curated part + assembly fixtures, each with an EXPECTED outcome
      ("pass"/"fail"). Run through the deterministic spine (no LLM), they are the
      tracked, visible set of extreme edge cases the platform must always handle.
      Add a row here whenever a new failure mode is discovered → the edge-case set
      is explicit and minimised over time.
CALLED BY: evaluation/run_eval.py, tests/test_eval.py.
"""
from __future__ import annotations


def _design(features, env=(130, 130, 60, 5)):
    return {"version": "1.0", "units": "mm", "process": "FDM",
            "envelope": {"x_mm": env[0], "y_mm": env[1], "z_mm": env[2], "tolerance_mm": env[3]},
            "features": features}


HUB = {"id": "hub", "type": "cylinder", "params": {"radius": 50, "height": 60}}
BORE = {"id": "bore", "type": "hole", "op": "cut", "target": "hub",
        "params": {"diameter": 15}, "asserts": {"bore_diameter_mm": 15}}


def _circular_features(item, count=7):
    return {"id": "fins", "type": "circular_pattern", "op": "union", "target": "hub",
            "params": {"count": count, "axis": [0, 0, 1], "feature": item},
            "asserts": {"count": count}}


_BOX_FEATURE = {"id": "f", "type": "box", "params": {"at": [45, 0, 0], "length": 40, "width": 2, "height": 60}}

PATTERN_SPEC = [
    {"id": "r1", "claim": "count", "target": "fins", "expected": 7, "severity": "required", "description": "7 features"},
    {"id": "r2", "claim": "feature_present", "target": "bore", "severity": "required", "description": "through bore"},
]


def _box_design(side, h, at=(0, 0, 0)):
    return {"version": "1.0", "units": "mm", "process": "FDM",
            "envelope": {"x_mm": side, "y_mm": side, "z_mm": h, "tolerance_mm": 3},
            "features": [{"id": "x", "type": "box",
                          "params": {"length": side, "width": side, "height": h, "at": list(at)}}]}


def _asm(mate_type="stack_on", params=None):
    return {"components": [{"id": "base", "grounded": True, "design": _box_design(40, 10)},
                           {"id": "top", "design": _box_design(40, 5)}],
            "mates": [{"type": mate_type, "a": "base", "b": "top", "params": params or {}}]}


CASES = [
    # ── parts (normal) ──
    {"name": "pattern_box_ok", "kind": "part", "expect": "pass",
     "ir": _design([HUB, _circular_features(_BOX_FEATURE), BORE]), "spec": PATTERN_SPEC},
    {"name": "bracket_bolts_ok", "kind": "part", "expect": "pass",
     "ir": {"version": "1.0", "units": "mm", "process": "CNC",
            "envelope": {"x_mm": 100, "y_mm": 100, "z_mm": 10, "tolerance_mm": 3},
            "features": [{"id": "plate", "type": "box", "params": {"length": 100, "width": 100, "height": 10}},
                         {"id": "bolts", "type": "circular_pattern", "op": "cut", "target": "plate",
                          "params": {"count": 4, "axis": [0, 0, 1],
                                     "feature": {"id": "h", "type": "hole", "params": {"at": [40, 0, 0], "diameter": 6}}},
                          "asserts": {"count": 4}}]},
     "spec": [{"id": "r1", "claim": "count", "target": "bolts", "expected": 4, "severity": "required", "description": "4 bolts"}]},
    # ── parts (extreme edge cases that MUST fail) ──
    {"name": "pattern_flat_features", "kind": "part", "expect": "fail",   # features embedded
     "ir": _design([HUB, {**_circular_features({**_BOX_FEATURE, "params": {**_BOX_FEATURE["params"], "at": [5, 0, 0]}}),
                           "asserts": {"count": 7}}, BORE]),
     "spec": PATTERN_SPEC},
    {"name": "pattern_wrong_count", "kind": "part", "expect": "fail",   # L2 count
     "ir": _design([HUB, _circular_features(_BOX_FEATURE, count=6), BORE]),
     "spec": [{**PATTERN_SPEC[0], "expected": 7}]},
    {"name": "feature_too_thick_8mm", "kind": "part", "expect": "fail",    # uniform_thickness
     "ir": _design([HUB, {**_circular_features(_BOX_FEATURE), "asserts": {"count": 7, "uniform_thickness_mm": 2}}, BORE],),
     "spec": [{"id": "r1", "claim": "uniform_thickness_mm", "target": "fins", "expected": 2, "severity": "required", "description": "2mm"}],
     "mutate_width": 8.0},
    {"name": "missing_required_param", "kind": "part", "expect": "fail",  # L1
     "ir": _design([{"id": "hub", "type": "cone", "params": {"r_top": 15, "height": 60}}]), "spec": []},
    # ── assemblies ──
    {"name": "assembly_stack_ok", "kind": "assembly", "expect": "pass", "asm": _asm(), "spec": []},
    {"name": "assembly_interference", "kind": "assembly", "expect": "fail",   # buried → collision
     "asm": _asm("custom", {"translate": [0, 0, 2]}), "spec": []},
    {"name": "assembly_floating", "kind": "assembly", "expect": "fail",       # far → not touching
     "asm": _asm("custom", {"translate": [0, 0, 50]}), "spec": []},
    {"name": "assembly_cycle", "kind": "assembly", "expect": "fail", "spec": [],  # L1 cycle
     "asm": {"components": [{"id": "a", "grounded": True, "design": _box_design(40, 10)},
                            {"id": "b", "design": _box_design(40, 5)},
                            {"id": "c", "design": _box_design(40, 4)}],
             "mates": [{"type": "stack_on", "a": "a", "b": "b"},
                       {"type": "stack_on", "a": "b", "b": "c"},
                       {"type": "stack_on", "a": "c", "b": "a"}]}},
    {"name": "assembly_no_grounded", "kind": "assembly", "expect": "fail", "spec": [],  # L1
     "asm": {"components": [{"id": "a", "design": _box_design(40, 10)},
                            {"id": "b", "design": _box_design(40, 5)}],
             "mates": [{"type": "stack_on", "a": "a", "b": "b"}]}},
]