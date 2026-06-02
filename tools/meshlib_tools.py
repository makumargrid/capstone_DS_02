"""
tools/meshlib_tools.py — the MeshLib Inspector Agent's function-tools.

USED BY: agents/meshlib_agent (registered via Agent(tools=[...])). Demoted L4:
         only invoked for `custom`/mesh_only nodes the deterministic L2 can't check.
WHEN EACH IS CALLED (by the meshlib agent, during a mesh inspection):
  explore_meshlib_api()  → when unsure of a mrmeshpy method name/signature.
  execute_meshlib_code() → to run a generated check script in the sandbox; retried
                           on crash_type until success or MAX_SCRIPTS_PER_RUN.
  set_run_context()      → NOT a model tool; the agent runner calls it to route
                           saved scripts to the current run dir.
CALLS: tools/meshlib_sandbox.py (run_in_sandbox); meshlib only inside the child.
"""
from __future__ import annotations
import os
import logging

from .meshlib_sandbox import run_in_sandbox

MAX_SCRIPTS_PER_RUN = 20  # hard cap; prevents crash-debug spirals

_script_counter = 0
_output_dir = "outputs/run_latest"
_outer_attempt = 1


def set_run_context(output_dir: str, outer_attempt: int) -> None:
    """Route saved scripts to the current run dir; reset the per-run counter."""
    global _script_counter, _output_dir, _outer_attempt
    _output_dir, _outer_attempt, _script_counter = output_dir, outer_attempt, 0


def execute_meshlib_code(script_content: str, mesh_path: str) -> dict:
    """Run a Python MeshLib script (meshlib.mrmeshpy) in an isolated subprocess.

    The script gets pre-defined `mesh` and `mesh_path`; it must fill a list
    `check_results` of dicts (check_name, measured, expected, passed, unit, reason).
    Returns {success, check_results, stderr, exit_code, crash_type, generated_code}.
    If crash_type is MAX_SCRIPTS_EXCEEDED, stop and emit findings so far.

    Args:
        script_content: the geometry-check Python script.
        mesh_path: absolute path to the mesh file.
    """
    global _script_counter
    _script_counter += 1
    if _script_counter > MAX_SCRIPTS_PER_RUN:
        return {"success": False, "check_results": [],
                "stderr": (f"MAX_SCRIPTS_PER_RUN ({MAX_SCRIPTS_PER_RUN}) exceeded. "
                           f"Stop tool calls and output JSON findings now."),
                "exit_code": -99, "crash_type": "MAX_SCRIPTS_EXCEEDED",
                "generated_code": script_content}
    try:
        os.makedirs(_output_dir, exist_ok=True)
        fn = os.path.join(_output_dir,
                          f"06c_outer{_outer_attempt}_ai_generated_meshlib_script_{_script_counter}.py")
        with open(fn, "w") as f:
            f.write(script_content)
    except Exception as e:
        logging.getLogger("google_adk").warning(f"Failed to save generated script: {e}")
    result = run_in_sandbox(script_content, mesh_path)
    # Inject rag_kb2 OCCT error context when a sandbox execution fails with a
    # known error pattern. The KB context is appended to stderr so the meshlib
    # inspector agent sees it on the NEXT retry, not before any code has run.
    if not result.get("success") and result.get("stderr"):
        try:
            from rag_kb2 import get_error_context as _kb2
            kb = _kb2(result["stderr"])
            if kb:
                result["stderr"] = result["stderr"] + "\n\n[KB_CONTEXT]\n" + kb
        except Exception:
            pass
    return result


def explore_meshlib_api(attribute_path: str = "") -> str:
    """Explore meshlib.mrmeshpy when unsure of a method name/arguments.

    Args:
        attribute_path: "" for top-level, "Mesh" for Mesh methods, etc.
    Returns a list of public attributes with brief docstrings.
    """
    import meshlib.mrmeshpy as mrmesh
    try:
        obj = mrmesh
        for part in (attribute_path.split('.') if attribute_path else []):
            obj = getattr(obj, part)
        public = [a for a in dir(obj) if not a.startswith('_')]
        out = f"Attributes of mrmeshpy.{attribute_path or 'mrmeshpy'}:\n"
        for i, a in enumerate(public):
            if i > 60:
                out += f"... and {len(public) - 60} more omitted.\n"
                break
            try:
                doc = (getattr(obj, a).__doc__ or "").strip().split('\n')[0][:120]
                out += f"- {a}: {doc}\n"
            except Exception:
                out += f"- {a}\n"
        return out
    except AttributeError:
        return f"Error: '{attribute_path}' not found in meshlib.mrmeshpy."
    except Exception as e:
        return f"Error exploring module: {e}"
