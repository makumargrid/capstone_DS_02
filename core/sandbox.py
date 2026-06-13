"""
core/sandbox.py — Sandboxed custom code execution for mesh_only/custom nodes.

Runs custom CadQuery code in a subprocess with enforced restrictions:
  - Wall-clock timeout (10s via subprocess.run timeout)
  - Credential stripping from environment
  - Temp-only working directory (chdir to disposable dir)
  - Network access blocked via socket guard in subprocess

What is NOT enforced (best-effort only):
  - CPU/memory resource limits (requires OS support not portable)
  - True filesystem isolation (chdir only; chroot not available)

CALLED BY: primitives/compiler.py::_run_custom
"""
from __future__ import annotations
import subprocess
import tempfile
import os
import json
import sys


SANDBOX_TIMEOUT_S = 10
SANDBOX_MEMORY_MB = 512


def run_custom_sandboxed(code: str) -> dict:
    """Run custom CadQuery code in a sandboxed subprocess.

    Args:
        code: the CadQuery Python code snippet to execute.

    Returns:
        JSON string from the subprocess: {"success": bool, "solid": str|None, "error": str|None}

    The subprocess writes a result JSON to a known temp file path.
    If the subprocess times out, exceeds memory, or fails, returns error JSON.
    """
    # Create a temp directory for the sandbox
    sandbox_dir = tempfile.mkdtemp(prefix="sandbox_custom_")
    output_path = os.path.join(sandbox_dir, "result.json")

    # The inner script to run in the subprocess
    inner_script = f"""
import os, sys, json, traceback
os.chdir({sandbox_dir!r})

# ── Restrict environment — remove all credentials ────────────────────────
for key in list(os.environ.keys()):
    if any(s in key.upper() for s in ('KEY', 'TOKEN', 'SECRET', 'PASS', 'CRED')):
        del os.environ[key]

# ── Block network access ─────────────────────────────────────────────────
import socket as _socket_module
_orig_socket = _socket_module.socket
class _BlockedSocket:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("Network access is blocked in sandbox")
    def __getattr__(self, name):
        raise RuntimeError("Network access is blocked in sandbox")
_socket_module.socket = _BlockedSocket
# Also block socket.create_connection (used by urllib)
def _blocked_connect(*args, **kwargs):
    raise RuntimeError("Network access is blocked in sandbox")
_socket_module.create_connection = _blocked_connect

try:
    import cadquery as cq
    import math

    scope = {{"cq": cq, "math": math, "result_solid": None}}
    exec({code!r}, scope)
    rs = scope.get("result_solid")

    if rs is None:
        result = {{"success": False, "error": "custom node did not assign 'result_solid'"}}
    else:
        if isinstance(rs, cq.Workplane):
            rs = rs.val()
        # Write solid to temp file
        solid_path = os.path.join({sandbox_dir!r}, "output.step")
        cq.exporters.export(rs, solid_path)
        # Return path relative to sandbox
        result = {{"success": True, "solid": solid_path, "error": None}}
except Exception as e:
    result = {{"success": False, "error": str(e), "traceback": traceback.format_exc()}}

with open({output_path!r}, "w") as f:
    json.dump(result, f)
"""

    try:
        # Run in subprocess with resource limits where available
        proc = subprocess.run(
            [sys.executable, "-c", inner_script],
            capture_output=True,
            text=True,
            timeout=SANDBOX_TIMEOUT_S,
            cwd=sandbox_dir,
            env={k: v for k, v in os.environ.items()
                 if not any(s in k.upper() for s in ('KEY', 'TOKEN', 'SECRET', 'PASS', 'CRED'))},
        )

        # Read the result JSON
        if os.path.isfile(output_path):
            with open(output_path) as f:
                result = json.load(f)
            return result
        else:
            return {"success": False, "error": f"Sandbox produced no output. stderr: {proc.stderr[:500]}"}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Custom code timed out after {SANDBOX_TIMEOUT_S}s"}
    except Exception as e:
        return {"success": False, "error": f"Sandbox execution failed: {e}"}
    finally:
        # Clean up sandbox directory
        import shutil
        try:
            shutil.rmtree(sandbox_dir, ignore_errors=True)
        except Exception:
            pass