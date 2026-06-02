"""
core/model_config.py — model resolution + ADK provider registry patch.

WHAT:
    get_model_name(role)          → model id for an agent role (from providers).
    get_fallback_model_name(role) → failover model id, or None.
    safe_parse_json(text)         → tolerant JSON extractor (shared by agents).
    Import-time: patches the ADK registry so each provider's models use the
                 correct ADK LLM class (driven entirely by core/providers.py).

CALLED BY: every agent (agents/*/agent.py), core/process_detector.py,
           core/llm_client.py, verification/* (safe_parse_json).
CALLS:     core/providers.py (the single provider switch-point), google.adk.
"""
from __future__ import annotations
import os
import re as _re
import json as _json
import logging

from . import providers

logger = logging.getLogger(__name__)


# ── Shared JSON parsing utility ─────────────────────────────────────────────
def safe_parse_json(text):
    """Parse a JSON object from text that may be fenced or wrapped in prose."""
    if not text:
        return None
    cleaned = _re.sub(r'```(?:json)?\s*', '', text).replace('```', '').strip()
    try:
        return _json.loads(cleaned)
    except _json.JSONDecodeError:
        pass
    start, end = cleaned.find('{'), cleaned.rfind('}')
    if start != -1 and end > start:
        try:
            return _json.loads(cleaned[start:end + 1])
        except _json.JSONDecodeError:
            pass
    return None


# ── ADK registry patch (provider-driven) ───────────────────────────────────
def _patch_adk_registry() -> None:
    """For each provider that declares an `adk_class`, point the ADK registry's
    matching model patterns at that class. Driven by core/providers.py, so a new
    provider is wired up by adding one PROVIDERS entry — nothing here changes."""
    try:
        from google.adk.models.registry import _llm_registry_dict
        import importlib
    except ImportError as e:
        logger.warning(f"Could not patch ADK registry: {e}")
        return

    for prov, spec in providers.PROVIDERS.items():
        cls_name, mod_name = spec.get("adk_class"), spec.get("adk_module")
        if not cls_name or not mod_name:
            continue
        try:
            cls = getattr(importlib.import_module(mod_name), cls_name)
        except (ImportError, AttributeError) as e:
            logger.warning(f"ADK class {mod_name}.{cls_name} for {prov} not found: {e}")
            continue
        for pattern in list(_llm_registry_dict.keys()):
            if spec["match"] in pattern:
                _llm_registry_dict[pattern] = cls
    logger.info("ADK registry patched from core/providers.py")


_patch_adk_registry()


# ── Public API ──────────────────────────────────────────────────────────────
def get_model_name(role: str = "planner") -> str:
    """Model id for `role`. If its provider key is missing, degrade to fallback."""
    model = providers.AGENT_MODELS.get(role)
    if model is None:
        logger.warning(f"Unknown role '{role}', defaulting to 'planner'")
        model = providers.AGENT_MODELS["planner"]
    prov = providers.provider_of(model)
    if prov and not providers.available(prov):
        fb = providers.fallback_model(role)
        if fb:
            logger.warning(f"[{role}] {model} provider key absent — degrading to {fb}")
            return fb
    return model


def get_fallback_model_name(role: str = "planner"):
    """Failover model id for `role`, or None if no distinct available provider."""
    return providers.fallback_model(role)
