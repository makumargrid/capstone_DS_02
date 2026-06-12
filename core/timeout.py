"""
core/timeout.py — operation timeout wrapper for compile/render/API calls.

WHAT: run_with_timeout(func, *args, timeout) runs `func(*args)` in a separate
      thread and returns (result, timed_out). On timeout, the call is cancelled
      (thread continues but pipeline moves on gracefully). Timeout errors are
      logged but never crash the pipeline — the operation is simply skipped.

WHY: CadQuery compilation, rendering, and LLM API calls can hang on complex
     geometry or network issues. Without timeouts, a single hung operation
     blocks the entire pipeline thread with no recovery.

CALLED BY: pipeline.py (compile, render, vision, meshlib stages).
CALLS: concurrent.futures.ThreadPoolExecutor.
"""
from __future__ import annotations
import concurrent.futures
import logging

_log = logging.getLogger("timeout")


def run_with_timeout(func, *args, timeout: float = 30, **kwargs):
    """Run `func(*args, **kwargs)` with a timeout.

    Returns (result, timed_out: bool). If timeout expires, returns (None, True).
    The thread continues running but the result is discarded — use only for
    operations that are safe to abandon (no partial state mutation).
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args, **kwargs)
        try:
            result = future.result(timeout=timeout)
            return result, False
        except concurrent.futures.TimeoutError:
            _log.warning(f"[TIMEOUT] {func.__name__} exceeded {timeout}s limit")
            return None, True
        except Exception:
            # Re-raise non-timeout exceptions so callers handle them normally
            raise