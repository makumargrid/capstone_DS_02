"""
core/registry.py — what happens AFTER the harness says APPROVED.

WHY: "APPROVED by the harness" ≠ "ACCEPTED by the user". Previously APPROVED just
     wrote files and returned — no record of intent-fidelity, no human sign-off.
WHAT:
  request_acceptance(interactive, summary) -> bool
        interactive: show the spec-coverage summary + view paths, ask accept/reject.
        non-interactive: auto-accept (records accepted_by="auto").
  record(out_dir, prompt, spec, ir, coverage, verdict, accepted) -> path
        appends one line to outputs/registry.jsonl AND writes the run's
        10_acceptance_record.json. This is the durable proof of what was
        delivered against what was asked.
CALLED BY: pipeline.py (after coverage-covered + harness APPROVED).
CALLS: stdlib only.
"""
from __future__ import annotations
import os
import sys
import json
import datetime

_REGISTRY = os.path.join("outputs", "registry.jsonl")


def request_acceptance(interactive: bool, summary: str) -> tuple[bool, str]:
    """Human acceptance gate. Returns (accepted, accepted_by)."""
    if interactive and sys.stdin.isatty():
        print("\n" + "=" * 60)
        print("ACCEPTANCE — does this match your intent?")
        print(summary)
        print("Accept this design? [y/N] ", end="", flush=True)
        ans = input().strip().lower()
        return (ans in ("y", "yes"), "user")
    return (True, "auto")  # non-interactive: harness-APPROVED stands, flagged auto


def record(out_dir: str, prompt: str, spec: list, ir: dict, coverage: dict,
           verdict: dict, accepted: bool, accepted_by: str) -> str:
    """Persist the acceptance record to the run dir + the global registry."""
    rec = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "run_dir": out_dir,
        "prompt": prompt,
        "spec": spec,
        "ir": ir,
        "coverage": coverage,
        "harness_verdict": verdict.get("decision"),
        "accepted": accepted,
        "accepted_by": accepted_by,
        "bundle": os.path.join(out_dir, "forgecad_handoff"),
    }
    with open(os.path.join(out_dir, "10_acceptance_record.json"), "w") as f:
        json.dump(rec, f, indent=2)
    os.makedirs(os.path.dirname(_REGISTRY), exist_ok=True)
    with open(_REGISTRY, "a") as f:
        f.write(json.dumps({k: rec[k] for k in
                ("timestamp", "run_dir", "prompt", "harness_verdict", "accepted", "accepted_by")}) + "\n")
    return _REGISTRY
