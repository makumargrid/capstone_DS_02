"""
evaluation/run_eval.py — deterministic evaluation harness (no LLM).

WHAT: runs every case in cases.CASES through the deterministic spine
      (validate → compile → inspect → coverage) and compares the actual
      pass/fail to the case's EXPECTED outcome. Emits a visible scorecard
      (evaluation/report/index.html) + summary.json. Reproducible + CI-able.
CALLED BY: `python -m evaluation.run_eval`, tests/test_eval.py.
CALLS: geometry_ir, primitives, verification, core.spec (all deterministic).
"""
from __future__ import annotations
import os
import copy
import json
import traceback

from geometry_ir import validate_plan
from geometry_ir.assembly import validate_assembly
from primitives import compile_design, compile_assembly
from verification import inspect_solid
from verification.assembly_inspector import inspect_assembly
from core.spec import check_coverage


def evaluate_case(case: dict) -> dict:
    """Return {name, kind, expect, actual('pass'/'fail'), ok, detail}."""
    name, kind, expect, spec = case["name"], case["kind"], case["expect"], case.get("spec", [])
    detail = ""
    try:
        if kind == "part":
            ir = copy.deepcopy(case["ir"])
            if "mutate_width" in case:   # build a too-thick feature to trip the thickness check
                ir["features"][1]["params"]["feature"]["params"]["width"] = case["mutate_width"]
            if not validate_plan(ir)["valid"]:
                actual, detail = "fail", "L1 invalid"
            else:
                solid, prov = compile_design(ir)
                l2 = inspect_solid(ir, solid, prov, min_wall_mm=0.5)
                cov = check_coverage(spec, l2["checks"], ir)
                actual = "pass" if (l2["valid"] and cov["covered"]) else "fail"
                detail = ("; ".join(l2["hard_failures"][:2])
                          or ("uncovered: " + ",".join(m["id"] for m in cov["missing"])))
        else:
            asm = case["asm"]
            if not validate_assembly(asm)["valid"]:
                actual, detail = "fail", "L1 invalid (" + validate_assembly(asm)["errors"][0]["detail"] + ")"
            else:
                compile_assembly(asm)
                l2 = inspect_assembly(asm, min_wall_mm=0.5)
                flat = {"features": [f for c in asm["components"] for f in c["design"]["features"]]}
                l2f = [{**c, "node": c["node"].split(".", 1)[-1]} for c in l2["checks"]]
                cov = check_coverage(spec, l2f, flat)
                actual = "pass" if (l2["valid"] and cov["covered"]) else "fail"
                detail = "; ".join(l2["hard_failures"][:2])
    except Exception as e:
        actual = "fail"
        detail = f"exception: {e}"
        traceback.print_exc()
    return {"name": name, "kind": kind, "expect": expect, "actual": actual,
            "ok": actual == expect, "detail": detail}


def run_all() -> list:
    from .cases import CASES
    return [evaluate_case(c) for c in CASES]


def write_scorecard(results: list, out_dir: str = "evaluation/report") -> str:
    os.makedirs(out_dir, exist_ok=True)
    passed = sum(r["ok"] for r in results)
    rows = "".join(
        f"<tr class='{'p' if r['ok'] else 'f'}'><td>{'✅' if r['ok'] else '❌'}</td>"
        f"<td>{r['name']}</td><td>{r['kind']}</td><td>{r['expect']}</td>"
        f"<td>{r['actual']}</td><td>{r['detail']}</td></tr>" for r in results)
    html = f"""<!doctype html><meta charset=utf-8><title>Eval scorecard</title>
<style>body{{font:14px system-ui;margin:24px}}table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #ddd;padding:6px 9px;text-align:left;font-size:13px}}
tr.p td{{background:#f1fbf3}}tr.f td{{background:#fdf1f1}}h1{{font-size:20px}}</style>
<h1>Deterministic eval — {passed}/{len(results)} cases as expected</h1>
<table><tr><th></th><th>case</th><th>kind</th><th>expected</th><th>actual</th><th>detail</th></tr>{rows}</table>"""
    with open(os.path.join(out_dir, "index.html"), "w") as f:
        f.write(html)
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump({"passed": passed, "total": len(results), "results": results}, f, indent=2)
    return os.path.join(out_dir, "index.html")


if __name__ == "__main__":
    res = run_all()
    path = write_scorecard(res)
    ok = sum(r["ok"] for r in res)
    for r in res:
        print(f"  {'OK ' if r['ok'] else 'XX '} {r['name']:26} expect={r['expect']:4} actual={r['actual']:4} {r['detail'][:50]}")
    print(f"\n{ok}/{len(res)} cases behaved as expected → {path}")
