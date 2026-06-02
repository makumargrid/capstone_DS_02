"""
verification/interface_inspector.py — L-ASM: deterministic interface verification.

WHY: independent part accuracy does NOT guarantee assembly accuracy. THIS layer is
     the deterministic answer to "combining isn't accurate" — it verifies every
     declared mate on the PLACED bodies: no unintended interference (collision),
     real contact (not floating), axis alignment (concentric), and fit/clearance.
WHAT: inspect_interfaces(assembly, placed) -> {valid, checks:[mate-keyed], hard_failures}
CALLED BY: verification/assembly_inspector.inspect_assembly, pipeline (Phase 2).
CALLS: cadquery (intersect volume, bounding boxes).
"""
from __future__ import annotations

EPS_INTERFERE = 1.0   # mm³ of overlap tolerated for a clearance mate (tessellation)
EPS_GAP = 0.5         # mm separation tolerated before parts count as "not touching"
ALIGN_TOL = 0.5       # mm axis-offset tolerated for concentric mates


def _result(node, claim, passed, measured, expected, detail=""):
    return {"node": node, "claim": claim, "passed": bool(passed),
            "measured": measured, "expected": expected, "detail": detail}


def _bbox_gap(A, B) -> float:
    """Separation between two AABBs (0 if overlapping/touching)."""
    a, b = A.BoundingBox(), B.BoundingBox()
    dx = max(a.xmin - b.xmax, b.xmin - a.xmax, 0.0)
    dy = max(a.ymin - b.ymax, b.ymin - a.ymax, 0.0)
    dz = max(a.zmin - b.zmax, b.zmin - a.zmax, 0.0)
    return (dx * dx + dy * dy + dz * dz) ** 0.5


def inspect_interfaces(assembly, placed: dict) -> dict:
    """Verify every declared mate on the placed bodies. `placed`={id: cq.Solid}."""
    mates = assembly["mates"] if isinstance(assembly, dict) else [m.model_dump() for m in assembly.mates]
    checks: list[dict] = []

    for m in mates:
        mtype, ma, mb = m["type"], m["a"], m["b"]
        params = m.get("params") or {}
        node = f"{ma}->{mb}"
        A, B = placed[ma], placed[mb]

        # 1. No unintended interference (collision). Press-fit may allow some overlap.
        vol = A.intersect(B).Volume()
        allow = params.get("interference_mm3", 0) if params.get("fit") == "interference" else EPS_INTERFERE
        checks.append(_result(node, "no_interference", vol <= allow, round(vol, 3), f"<= {allow}",
                              f"{mtype}: overlap volume mm³"))

        # 2. Real contact (not floating).
        gap = _bbox_gap(A, B)
        checks.append(_result(node, "contact", gap <= EPS_GAP, round(gap, 3), f"<= {EPS_GAP}",
                              "components must actually touch/mate"))

        # 3. Concentric alignment + optional fit.
        if mtype == "concentric":
            ca, cb = A.Center(), B.Center()
            off = ((ca.x - cb.x) ** 2 + (ca.y - cb.y) ** 2) ** 0.5
            checks.append(_result(node, "concentric_alignment", off <= ALIGN_TOL,
                                  round(off, 3), f"<= {ALIGN_TOL}", "axis offset"))
            bore, shaft = params.get("bore_mm"), params.get("shaft_mm")
            if bore and shaft:
                clr = bore - shaft
                ok = (clr >= 0) if params.get("fit", "clearance") != "interference" else (clr <= 0)
                checks.append(_result(node, "fit", ok, round(clr, 3),
                                      params.get("fit", "clearance"), "bore-shaft clearance mm"))

    hard = [c for c in checks if not c["passed"]]
    return {"valid": not hard, "checks": checks,
            "hard_failures": [f"{c['node']}.{c['claim']}: measured {c['measured']} expected {c['expected']}"
                              for c in hard]}
