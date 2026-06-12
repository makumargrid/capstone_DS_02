"""
agents/meshlib_agent — MeshLib Inspector Agent (findings-only, DEMOTED to L4).

ROLE: AI-assisted mesh inspection for `custom`/mesh_only nodes the deterministic
      L2 inspector cannot check. Reports findings ONLY — never a pass/fail verdict.
TOOLS (registered via Agent(tools=[...])): tools/meshlib_tools.py
      execute_meshlib_code, explore_meshlib_api.
CALLED BY: pipeline.py (only when a feature is mesh_only).
CALLS: core/model_config (model + safe_parse_json), tools/meshlib_tools
       (+ set_run_context, run_invariant_baseline via the sandbox).
"""
import json
import os
os.environ['GOOGLE_GENAI_USE_VERTEXAI'] = 'false'

from google.adk.agents import Agent
from google.genai import types

from core.model_config import get_model_name, safe_parse_json
from core.adk_runner import run_agent
from tools.meshlib_tools import execute_meshlib_code, explore_meshlib_api, set_run_context
from tools.meshlib_sandbox import run_invariant_baseline

try:
    from rag_kb2 import get_error_context as _get_kb2_context
except ImportError:
    def _get_kb2_context(tb): return ""  # graceful no-op if rag_kb2 not available


INSTRUCTION = """You are a MeshLib Geometry Inspector. You analyze 3D mesh files against design specifications.

CRITICAL: You report FINDINGS ONLY. You do NOT decide whether the design passes or fails.
A separate Reviewer Agent will make that decision based on your findings.

Your workflow:
1. Read the design brief to understand every declared dimension and feature.
2. Identify which properties are measurable with MeshLib.
3. If you do not know the exact MeshLib function, use `explore_meshlib_api` to discover it.
4. Write Python code using the discovered APIs.
5. Call `execute_meshlib_code` to run the code.
6. If the tool returns success=False, rewrite the code to fix the crash_type issue.
   If [KB_CONTEXT] is present above, apply its fix advice first before guessing.
   EXCEPTION: If crash_type is "MAX_SCRIPTS_EXCEEDED", STOP ALL tool calls immediately
   and output your JSON findings based on whatever checks completed so far.
7. Report ALL findings — passed checks AND failed checks — with exact measurements.

Generated Code Rules:
- `mesh` and `mesh_path` are pre-defined. NEVER redefine or load them.
- Only import: `import meshlib.mrmeshpy as mrmesh`.
- Populate the pre-defined list `check_results` with dicts having keys:
  "check_name", "measured", "expected", "passed", "unit", "reason".
- DO NOT wrap in try/except. Let errors propagate for crash detection.
- Never write files, read files (other than mesh_path), or make network calls.

Focus on what only you can do: feature counts, protrusion/taper at key Z levels,
angular spacing/twist, bore diameter top & bottom, and FDM overhang %.
Do NOT re-measure wall thickness or bounding box (already in the baseline).

Output ONLY a JSON object (no markdown):
{
  "checks": [{"check_name","measured","expected","tolerance","passed","unit","reason"}],
  "anomalies": ["..."],
  "engineer_summary": "one paragraph",
  "confidence": "HIGH | MEDIUM | LOW"
}
"""

def _make_agent(model: str) -> Agent:
    return Agent(name="meshlib_inspector", model=model,
                 description="Inspects 3D mesh files against a design spec using MeshLib. Findings only — no verdict.",
                 instruction=INSTRUCTION, tools=[execute_meshlib_code, explore_meshlib_api])


# module-level agent for `adk web`; runtime uses run_agent (with failover).
root_agent = _make_agent(get_model_name("inspector"))


def run_inspection(mesh_path: str, design_brief: dict, output_dir: str, outer_attempt: int = 1) -> dict:
    """Run the MeshLib inspection agent; return structured findings (checks,
    anomalies, engineer_summary, confidence)."""
    set_run_context(output_dir, outer_attempt)

    baseline = run_invariant_baseline(mesh_path)
    if baseline.get("load_failed"):
        return {"checks": [], "anomalies": [f"Mesh load failed: {baseline.get('hard_failures', ['?'])[0]}"],
                "engineer_summary": "The mesh file could not be loaded.", "confidence": "HIGH"}

    # rag_kb2 error context is injected by execute_meshlib_code() in tools/meshlib_tools.py
    # when a sandbox execution fails — it's appended to stderr so the inspector sees it on
    # the retry. No pre-injection here (baseline dict doesn't contain OCCT tracebacks).

    # Inject CadQuery API reference context for custom/mesh_only nodes so the inspector
    # has method signatures and examples when writing custom check scripts.
    kb1_context = ""
    try:
        from rag_kb1 import get_api_context
        kb1_context = get_api_context(design_brief, design_brief.get("prompt", ""))
    except Exception:
        pass

    message = (f"Mesh Path: {mesh_path}\n\nDesign Brief:\n{json.dumps(design_brief, indent=2)}\n\n"
               f"Baseline Results:\n{json.dumps(baseline, indent=2)}\n\n"
               f"Baseline already covered watertightness/volume/self-intersections/bbox — "
               f"do not repeat. Focus on plan-specific feature verification.")
    if kb1_context:
        message += "\n\n" + kb1_context

    content = types.Content(role='user', parts=[types.Part(text=message)])
    final_text, events = run_agent(_make_agent, content, role="inspector", app_name="meshlib_agent")

    if final_text:
        findings = safe_parse_json(final_text)
        if findings is not None:
            for k in ("checks", "anomalies", "engineer_summary", "confidence"):
                findings.setdefault(k, [] if k in ("checks", "anomalies") else None)
            try:
                os.makedirs(output_dir, exist_ok=True)
                with open(os.path.join(output_dir, f"06b_outer{outer_attempt}_ai_inspector_conversation_trace.json"), "w") as f:
                    json.dump([e.model_dump(mode='json') for e in events], f, indent=4)
            except Exception:
                pass
            return findings

    return {"checks": [], "anomalies": [f"Could not parse agent response: {final_text}"],
            "engineer_summary": final_text or "No response from agent.", "confidence": "LOW"}
