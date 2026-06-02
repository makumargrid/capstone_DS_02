"""
reporting/report.py — one human-readable, self-contained report per run.

WHAT: build_report(run_dir) assembles a single `report.html` you open in a browser
      to SEE the whole run: prompt, process, extracted spec, decomposition decision,
      the node-keyed check table (L2 + interfaces), the coverage table, the reviewer
      verdict, the acceptance record, and the rendered multi-view PNGs (embedded as
      base64 so the file is portable). Works for part OR assembly runs, pass or fail.
CALLED BY: pipeline.py (at the end of every run).
CALLS: stdlib only (reads the run's JSON/PNG artifacts).
"""
from __future__ import annotations
import os
import glob
import json
import base64


def _read(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def _latest(run_dir, pattern):
    """Return the highest-iteration file matching e.g. '05_outer*_*.json'."""
    files = sorted(glob.glob(os.path.join(run_dir, pattern)))
    return files[-1] if files else None


def _check_rows(checks):
    rows = []
    for c in checks or []:
        ok = "✅" if c.get("passed") else "❌"
        rows.append(f"<tr class='{'p' if c.get('passed') else 'f'}'><td>{ok}</td>"
                    f"<td>{c.get('node','')}</td><td>{c.get('claim','')}</td>"
                    f"<td>{c.get('measured','')}</td><td>{c.get('expected','')}</td></tr>")
    return "".join(rows)


def _img(path):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    name = os.path.basename(path)
    return f"<figure><img src='data:image/png;base64,{b64}'><figcaption>{name}</figcaption></figure>"


def build_report(run_dir: str) -> str:
    brief = _read(os.path.join(run_dir, "01_design_brief.json")) or {}
    spec = _read(os.path.join(run_dir, "01b_spec.json")) or []
    decomp = _read(os.path.join(run_dir, "01c_decomposition.json")) or {}
    insp = _read(_latest(run_dir, "05_outer*_solid_inspection.json")
                 or _latest(run_dir, "05_outer*_assembly_inspection.json") or "") or {}
    cov = _read(_latest(run_dir, "08_outer*_spec_coverage.json") or "") or {}
    verdict = _read(_latest(run_dir, "07_outer*_reviewer_verdict.json") or "") or {}
    accepted = _read(os.path.join(run_dir, "10_acceptance_record.json")) or {}
    views = sorted(glob.glob(os.path.join(run_dir, "09_outer*_view_*.png")) +
                   glob.glob(os.path.join(run_dir, "09_outer*_assembly_*.png")))
    # keep only the latest iteration's views
    if views:
        last_pref = os.path.basename(views[-1]).split("_view_")[0].split("_assembly_")[0]
        views = [v for v in views if os.path.basename(v).startswith(last_pref)]

    spec_rows = "".join(f"<tr><td>{r.get('claim')}</td><td>{r.get('target','')}</td>"
                        f"<td>{r.get('expected','')}</td><td>{r.get('severity','')}</td>"
                        f"<td>{r.get('description','')}</td></tr>" for r in spec)
    cov_rows = "".join(f"<tr class='{'p' if c.get('covered') else 'f'}'>"
                       f"<td>{'✅' if c.get('covered') else '❌'}</td><td>{c.get('id','')}</td>"
                       f"<td>{c.get('claim','')}</td><td>{c.get('target','')}</td></tr>"
                       for c in (cov.get("report") or []))
    dec = verdict.get("decision", "—")
    acc = f"{accepted.get('accepted')} (by {accepted.get('accepted_by')})" if accepted else "—"

    html = f"""<!doctype html><meta charset=utf-8><title>Run report — {os.path.basename(run_dir)}</title>
<style>body{{font:14px system-ui;margin:24px;color:#111;max-width:1100px}}
h1{{font-size:20px}}h2{{font-size:15px;margin-top:28px;border-bottom:1px solid #ddd;padding-bottom:4px}}
table{{border-collapse:collapse;width:100%;margin:8px 0}}td,th{{border:1px solid #ddd;padding:5px 8px;text-align:left;font-size:13px}}
tr.p td{{background:#f1fbf3}}tr.f td{{background:#fdf1f1}}
.badge{{display:inline-block;padding:3px 10px;border-radius:4px;color:#fff;font-weight:600}}
.APPROVED{{background:#1a9850}}.REDESIGN{{background:#d97706}}.HALT,.—{{background:#888}}
figure{{display:inline-block;margin:6px;text-align:center}}img{{width:300px;border:1px solid #ccc}}
figcaption{{font-size:11px;color:#666}}pre{{background:#f6f6f6;padding:8px;overflow:auto;font-size:12px}}</style>
<h1>Run report — {os.path.basename(run_dir)}</h1>
<p><b>Verdict:</b> <span class='badge {dec}'>{dec}</span> &nbsp; <b>Accepted:</b> {acc}
&nbsp; <b>Process:</b> {brief.get('process','?')} &nbsp; <b>Mode:</b> {decomp.get('mode','part')}</p>
<h2>Prompt</h2><pre>{brief.get('prompt','')}</pre>
<h2>Decomposition decision</h2><p>{decomp.get('rationale','(monolithic part)')}</p>
<h2>Intent spec ({len(spec)} requirements)</h2>
<table><tr><th>claim</th><th>target</th><th>expected</th><th>severity</th><th>description</th></tr>{spec_rows}</table>
<h2>Verification checks (L2 + interfaces)</h2>
<table><tr><th></th><th>node</th><th>claim</th><th>measured</th><th>expected</th></tr>{_check_rows(insp.get('checks'))}</table>
<h2>Spec coverage</h2>
<table><tr><th></th><th>id</th><th>claim</th><th>target</th></tr>{cov_rows or '<tr><td colspan=4>—</td></tr>'}</table>
<h2>Reviewer reasoning</h2><pre>{verdict.get('reasoning','')}</pre>
<h2>Rendered views</h2>{''.join(_img(v) for v in views) or '<p>(none)</p>'}
"""
    path = os.path.join(run_dir, "report.html")
    with open(path, "w") as f:
        f.write(html)
    return path
