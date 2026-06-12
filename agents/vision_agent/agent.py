"""
Vision Verifier Agent (L3) — "Thinking with Images".

A multimodal ADK agent that looks at the rendered multi-view PNGs and judges,
against the IR's declared intent, whether the expected features are present, the
orientation is sane, and there are no gross visual defects. It is a SECONDARY
signal: the deterministic L2 inspector is ground truth; vision catches things
that are easier to see than to measure (missing/merged features, wrong shape).

Findings are advisory and carry a confidence — the reviewer (Task 6) trusts L2
over vision on any conflict.

Tool registration: this agent has NO tools; images are passed as `types.Part`
inline-data parts in the user `Content` (the standard ADK multimodal pattern).
The model is selected via `src.model_config.get_model_name("inspector")`.
"""
from __future__ import annotations
import os
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "false")

import json
import uuid
import asyncio
import logging

from google.adk.agents import Agent
from google.genai import types

from core.model_config import get_model_name, safe_parse_json
from core.adk_runner import run_agent

import os as _os
_SKILL_DIR = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))), "skills", "vision")
with open(_os.path.join(_SKILL_DIR, "SKILL.md")) as _f:
    INSTRUCTION = _f.read()

def _make_agent(model: str) -> Agent:
    return Agent(name="vision_verifier", model=model,
                 description="Multimodal verifier that judges rendered CAD views against design intent. Advisory findings only.",
                 instruction=INSTRUCTION, tools=[])  # images passed as inline Parts


# module-level agent for `adk web`; runtime uses run_agent (with failover).
root_agent = _make_agent(get_model_name("vision"))


def _img_part(path: str) -> types.Part:
    with open(path, "rb") as f:
        return types.Part(inline_data=types.Blob(mime_type="image/png", data=f.read()))


def run_vision_verification(view_paths: dict, design_intent: dict) -> dict:
    """Run the Vision Verifier over rendered views.

    Args:
        view_paths: {view_name: png_path} from renderer.render_views.
        design_intent: compact IR intent (features + envelope) for context.

    Returns:
        Structured findings dict (see INSTRUCTION schema), or a LOW-confidence
        fallback if the agent/model is unavailable.
    """
    parts = [types.Part(text=(
        "Design intent (Geometry IR):\n" + json.dumps(design_intent, indent=2) +
        "\n\nThe following views are labelled front/side/top/iso/section. "
        "Verify the part against the intent and return the JSON findings."))]
    for name in ("front", "side", "top", "iso", "section"):
        if name in view_paths and os.path.exists(view_paths[name]):
            parts.append(types.Part(text=f"View: {name}"))
            parts.append(_img_part(view_paths[name]))

    content = types.Content(role="user", parts=parts)
    final, _events = run_agent(_make_agent, content, role="vision", app_name="vision_agent")
    parsed = safe_parse_json(final) if final else None
    if parsed is None:
        return {"features_present": {}, "shape_plausible": None,
                "observations": ["could not parse vision response"],
                "suspected_defects": [], "confidence": "LOW"}
    for k, default in (("features_present", {}), ("shape_plausible", None),
                       ("observations", []), ("suspected_defects", []),
                       ("confidence", "LOW")):
        parsed.setdefault(k, default)
    return parsed
