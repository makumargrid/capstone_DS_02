"""
geometry_ir/assembly.py — the Assembly IR contract (Phase 2).

WHAT: an Assembly is a tree of COMPONENTS (each a full Design) joined by MATES
      (declared interface contracts). One component is `grounded` (fixed at the
      origin); every other is placed RELATIVE to a placed neighbour via a mate.
      Crucially the planner declares mate INTENT — it does NOT compute transforms
      (primitives/assembly.py solves them), which is what keeps the merge robust.
CALLED BY: primitives/assembly.py (solve+compile), pipeline (Phase 2c).
CALLS: pydantic; geometry_ir/models.py (Design).

validate_assembly enforces: exactly one grounded; mate endpoints exist; the mate
graph spans ALL components and is acyclic (a grounded kinematic tree — no floats,
no over-constraint).
"""
from __future__ import annotations
from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

from .models import Design, Envelope, IR_VERSION

MATE_TYPES = ("stack_on", "concentric", "coincident_face", "custom")


class Component(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    design: Design
    grounded: bool = False


class Mate(BaseModel):
    """Declared interface. `a` is the (already-placed) reference; `b` is placed
    relative to it. `params` carries mate-specific data (e.g. z offset, or the
    explicit transform for `custom`)."""
    model_config = ConfigDict(extra="forbid")
    type: Literal["stack_on", "concentric", "coincident_face", "custom"]
    a: str
    b: str
    params: dict[str, Any] = Field(default_factory=dict)


class Assembly(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str = IR_VERSION
    units: Literal["mm"] = "mm"
    process: str = "FDM"
    kind: Literal["assembly"] = "assembly"
    components: list[Component] = Field(min_length=1)
    mates: list[Mate] = Field(default_factory=list)
    envelope: Optional[Envelope] = None


def validate_assembly(asm: dict | Assembly) -> dict:
    """Return {valid, errors:[{node, detail}]} for an Assembly IR."""
    errors: list[dict] = []
    if isinstance(asm, Assembly):
        a = asm
    else:
        try:
            a = Assembly.model_validate(asm)
        except Exception as e:
            return {"valid": False, "errors": [{"node": "assembly", "detail": str(e)}]}

    ids = [c.id for c in a.components]
    if len(set(ids)) != len(ids):
        errors.append({"node": "assembly", "detail": "duplicate component ids"})
    grounded = [c.id for c in a.components if c.grounded]
    if len(grounded) != 1:
        errors.append({"node": "assembly",
                       "detail": f"exactly one component must be grounded (got {len(grounded)})"})

    idset = set(ids)
    for m in a.mates:
        for end in (m.a, m.b):
            if end not in idset:
                errors.append({"node": f"mate:{m.a}->{m.b}", "detail": f"unknown component '{end}'"})

    # Mate graph must span all components and be acyclic (grounded tree).
    if not errors and len(a.components) > 1:
        adj: dict[str, list[str]] = {i: [] for i in ids}
        for m in a.mates:
            adj[m.a].append(m.b)
            adj[m.b].append(m.a)
        seen, stack, parent = set(), [grounded[0]], {grounded[0]: None}
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            for nb in adj[n]:
                if nb not in seen:
                    parent[nb] = n
                    stack.append(nb)
                elif parent.get(n) != nb:
                    errors.append({"node": "assembly", "detail": f"mate graph has a cycle near '{n}'"})
                    break
        floating = idset - seen
        if floating:
            errors.append({"node": "assembly",
                           "detail": f"components not connected to grounded base: {sorted(floating)}"})

    return {"valid": not errors, "errors": errors}
