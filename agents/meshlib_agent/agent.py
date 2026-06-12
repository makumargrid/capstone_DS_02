"""
agents/meshlib_agent — Deterministic Mesh Inspector (Prompt 11).

ROLE: Fixed geometric battery for `custom`/mesh_only nodes.
      No runtime LLM-generated measurement code — deterministic, repeatable.
      Reports findings ONLY — never a pass/fail verdict.

TOOLS: The script-rewrite loop is retired. The agent is a thin shell that
       delegates to run_invariant_baseline (fixed seed, deterministic).

CALLED BY: pipeline.py (only when a feature is mesh_only).
"""
import json
import os
os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'false'

from google.adk.agents import Agent
from core.model_config import get_model_name
from tools.meshlib_sandbox import run_invariant_baseline


import os as _os
_SKILL_DIR = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))), "skills", "meshlib")
with open(_os.path.join(_SKILL_DIR, "SKILL.md")) as _f:
    INSTRUCTION = _f.read()


def _make_agent(model: str) -> Agent:
    return Agent(name="meshlib_inspector", model=model,
                 description="Deterministic mesh inspection — fixed geometric battery, no runtime LLM measurement code. Findings only.",
                 instruction=INSTRUCTION, tools=[])


# module-level agent for `adk web`; runtime uses deterministic battery.
root_agent = _make_agent(get_model_name("inspector"))


def run_inspection(mesh_path: str, design_brief: dict, output_dir: str, outer_attempt: int = 1) -> dict:
    """Run deterministic mesh inspection (no LLM, no script loop).
    
    Returns structured findings from the fixed geometric battery:
    volume, watertightness, self-intersections, bounding box.
    For custom/mesh_only nodes, these are the AUTHORITATIVE results.

    Invariant: same mesh → identical measurements on repeat runs.
    """
    baseline = run_invariant_baseline(mesh_path)
    if baseline.get("load_failed"):
        return {"checks": [], "anomalies": [f"Mesh load failed: {baseline.get('hard_failures', ['?'])[0]}"],
                "engineer_summary": "The mesh file could not be loaded.", "confidence": "HIGH",
                "deterministic": True, "method": "fixed_geometric_battery"}

    # Convert baseline results to check format
    checks = []
    for item in baseline.get("baseline", []):
        checks.append({
            "check_name": item.get("check", "unknown"),
            "measured": item.get("value"),
            "expected": item.get("expected"),
            "passed": item.get("passed", True),
            "unit": item.get("unit", ""),
            "reason": item.get("detail", ""),
        })
    
    # Add load success check
    checks.append({
        "check_name": "mesh_load",
        "measured": True,
        "expected": True,
        "passed": True,
        "unit": "",
        "reason": "Mesh file loaded successfully",
    })

    return {
        "checks": checks,
        "anomalies": baseline.get("hard_failures", []),
        "engineer_summary": (
            f"Deterministic mesh inspection complete. "
            f"{len([c for c in checks if c['passed']])}/{len(checks)} checks passed. "
            f"No LLM-generated measurement code was used."
        ),
        "confidence": "HIGH",
        "deterministic": True,
        "method": "fixed_geometric_battery",
    }