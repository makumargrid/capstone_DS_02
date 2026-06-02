"""
core/_quiet.py — fully suppress the benign 'Event loop is closed' teardown race.

ROOT CAUSE: ADK's synchronous Runner.run() creates an asyncio loop per LLM call,
makes the request over an httpx ASYNC client, then closes the loop. The SDK's
httpx client defers connection-pool cleanup, so a pending socket aclose() can fire
on the now-closed loop → RuntimeError('Event loop is closed'). The response has
ALREADY arrived — this is a post-completion teardown race, not a real failure.

It surfaces TWO ways; we neutralise BOTH (and ONLY this exact message):
  1. as an *unraisable* exception        → sys.unraisablehook
  2. as an asyncio Task whose exception  → a filter on the 'asyncio' logger
     is "never retrieved" (logged at GC)   (checks the record's exc_info too)
Imported once by core/__init__.py.
"""
import sys
import logging

# 1) unraisable path
_original = sys.unraisablehook


def _hook(unraisable):
    if (unraisable.exc_type is RuntimeError
            and "Event loop is closed" in str(unraisable.exc_value)):
        return
    _original(unraisable)


sys.unraisablehook = _hook


# 2) asyncio "Task exception was never retrieved" path
class _DropLoopClosed(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        exc = record.exc_info[1] if record.exc_info else None
        if exc is not None and "Event loop is closed" in str(exc):
            return False
        return "Event loop is closed" not in record.getMessage()


logging.getLogger("asyncio").addFilter(_DropLoopClosed())
