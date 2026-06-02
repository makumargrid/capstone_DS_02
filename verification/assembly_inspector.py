"""
verification/assembly_inspector.py — verify a whole assembly.

WHAT: inspect_assembly(assembly) runs Phase-1 L2 on EACH component (so every part
      is independently correct) AND the L-ASM interface checks on the placed bodies
      (so the merge is correct). One combined node-keyed report — the reviewer and
      coverage gate consume it exactly like a single part's L2.
CALLED BY: pipeline (assembly route).
CALLS: primitives.assembly.place_components, verification.solid_inspector.inspect_solid,
       verification.interface_inspector.inspect_interfaces.
"""
from __future__ import annotations

from primitives.assembly import place_components
from .solid_inspector import inspect_solid
from .interface_inspector import inspect_interfaces


def inspect_assembly(assembly, min_wall_mm: float = 2.0) -> dict:
    """Per-component L2 + interface verification → one {valid, checks, hard_failures}."""
    cc = place_components(assembly)
    checks: list[dict] = []

    # 1. Each component must be independently correct (Phase-1 L2), node-prefixed.
    for cid, d in cc.items():
        l2 = inspect_solid(d["design"], d["local"], d["prov"], min_wall_mm=min_wall_mm)
        for c in l2["checks"]:
            checks.append({**c, "node": f"{cid}.{c['node']}"})

    # 2. Interfaces must be correct (the merge).
    placed = {cid: d["placed"] for cid, d in cc.items()}
    checks += inspect_interfaces(assembly, placed)["checks"]

    hard = [c for c in checks if not c["passed"]]
    return {"valid": not hard, "checks": checks,
            "hard_failures": [f"{c['node']}.{c['claim']}: measured {c['measured']} expected {c['expected']}"
                              for c in hard]}
