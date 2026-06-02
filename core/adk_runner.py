"""
core/adk_runner.py — run a stateless ADK agent with provider failover.

WHAT: run_agent(make_agent, content, role, app_name) builds the agent for the
      role's primary model, runs it to completion (tool loops included), and on
      an exception OR empty response rebuilds with the role's fallback model
      (Claude→Gemini). Returns (final_text, events).
WHY: the planner had failover but vision/meshlib/reviewer did not — so when one
     provider was down (e.g. quota) they crashed with ADK tracebacks. This makes
     failover shared infra, driven by core/providers.py.
CALLED BY: agents/vision_agent, agents/meshlib_agent, agents/reviewer_agent.
CALLS: google.adk (Runner, Agent built by `make_agent(model)`), core/model_config.
NOTE: stateless (fresh session per run). The planner keeps its own persistent-
      session runtime (IRPlanner) because it needs context across iterations.
"""
from __future__ import annotations
import uuid
import asyncio
import logging
from typing import Callable

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from .model_config import get_model_name, get_fallback_model_name

_log = logging.getLogger("adk_runner")


def run_agent(make_agent: Callable, content, role: str, app_name: str):
    """Run `make_agent(model)` on `content` with primary→fallback model failover.

    Returns (final_text, events). On total failure returns ("", [])."""
    models = [get_model_name(role)]
    fb = get_fallback_model_name(role)
    if fb and fb not in models:
        models.append(fb)

    for model in models:
        try:
            ss = InMemorySessionService()
            sid = str(uuid.uuid4())
            asyncio.run(ss.create_session(app_name=app_name, user_id="user", session_id=sid))
            runner = Runner(agent=make_agent(model), app_name=app_name, session_service=ss)
            events = list(runner.run(user_id="user", session_id=sid, new_message=content))
            text = ""
            for ev in events:
                if ev.is_final_response() and ev.content and ev.content.parts:
                    text = ev.content.parts[0].text or ""
                    break
            if text.strip():
                return text, events
            _log.warning(f"{app_name} on {model}: empty response; trying next model")
        except Exception as e:
            _log.warning(f"{app_name} on {model} failed: {e}; trying next model")
    return "", []
