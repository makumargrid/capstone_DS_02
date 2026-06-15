"""
core/llm_client.py — direct (non-ADK) LLM call with provider failover.

WHAT: call_llm(model, contents, system_prompt) makes a one-shot completion using
      the native provider SDK (anthropic / google-genai), retrying and then
      failing over to a Gemini model. Used for lightweight, tool-free calls
      where spinning up an ADK agent is unnecessary.
CALLED BY: core/process_detector.py (Stage-2 process classification).
CALLS: core/logger.py; anthropic / google.genai SDKs; reads *_API_KEY env vars.

NOTE: ADK-based agents (planner/vision/reviewer/meshlib) do NOT use this — they
      go through google.adk with models resolved by core/model_config.py.
"""
from __future__ import annotations
import os
import time

from .env import bootstrap_env
bootstrap_env()
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "false"  # force Developer API (ignore inherited Vertex env)

from google import genai
from .logger import get_agent_logger

logger = get_agent_logger()


def call_llm(model_name: str, contents: str, system_prompt: str | None = None) -> str:
    """Generate content with retries + Gemini failover. Returns the text."""
    models_to_try = [model_name]
    if "gemini" not in model_name:
        models_to_try.append("gemini-3.1-pro-preview")
    if "gemini-3.5-flash" not in models_to_try:
        models_to_try.append("gemini-3.5-flash")

    last_error = None
    for model in models_to_try:
        for attempt in range(3):
            try:
                logger.info(f"call_llm: {model} (attempt {attempt + 1}/3)")
                if "claude" in model:
                    import anthropic
                    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
                    kwargs = {"model": model, "max_tokens": 4096,
                              "messages": [{"role": "user", "content": contents}]}
                    if system_prompt:
                        kwargs["system"] = system_prompt
                    return client.messages.create(**kwargs).content[0].text
                client = genai.Client(vertexai=False, api_key=os.environ.get("GEMINI_API_KEY"))
                full = f"{system_prompt}\n\n{contents}" if system_prompt else contents
                return client.models.generate_content(model=model, contents=full).text or ""
            except Exception as e:
                last_error = e
                logger.warning(f"call_llm error on {model} attempt {attempt + 1}: {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
        logger.error(f"All attempts failed for {model}; trying next model.")
    if last_error is None:
        raise RuntimeError("All LLM attempts failed but no exception was recorded")
    raise last_error

