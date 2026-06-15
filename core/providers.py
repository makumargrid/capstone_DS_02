"""
core/providers.py — THE single switch-point for LLM providers.

WHY THIS FILE EXISTS (granular modularity):
    Everything provider-specific lives here. To swap Anthropic→Gemini, change a
    model string in AGENT_MODELS. To add OpenAI, add one PROVIDERS entry. To
    re-order failover, edit FALLBACK_ORDER. No agent or pipeline code changes.

WHAT:
    PROVIDERS      — per-provider rules (name match, ADK class, API-key env var).
    AGENT_MODELS   — which model each agent role uses (the swap dial).
    FALLBACK_ORDER — provider preference when a role's model is unavailable.
    provider_of(model) / fallback_model(role) / available(provider) helpers.

CALLED BY: core/model_config.py (model resolution + ADK registry patch),
           agents/planner_agent/agent.py (runtime Claude→Gemini failover).
CALLS:     os.environ only (key presence). Pure config — no heavy imports.
"""
from __future__ import annotations
import os
from .env import bootstrap_env

bootstrap_env()

# ── Provider catalogue ──────────────────────────────────────────────────────
# `match`     : substring identifying a model id as belonging to this provider.
# `adk_class` : ADK LLM class to register for this provider's models, or None
#               when ADK's default (google-genai) already handles it.
# `key_env`   : environment variable holding the provider's API key.
PROVIDERS: dict[str, dict] = {
    "anthropic": {"match": "claude", "adk_module": "google.adk.models.anthropic_llm",
                  "adk_class": "AnthropicLlm", "key_env": "ANTHROPIC_API_KEY"},
    "google":    {"match": "gemini", "adk_module": None, "adk_class": None, "key_env": "GEMINI_API_KEY"},
    # To add OpenAI: "openai": {"match": "gpt", "adk_module": "<module>", "adk_class": "<Class>", "key_env": "OPENAI_API_KEY"},
}

# ── The swap dial: which model LEADS each role (capability-based) ────────────
# Rationale (edit any value to swap; the OTHER family is the automatic fallback):
#   Claude  → precise structured code/IR, strict schema, multi-constraint
#             instruction-following, tool use  → planner, meshlib inspector.
#   Gemini  → native multimodal/vision + large-context analytical reasoning
#             → vision verifier, reviewer, and intent extraction.
#   Intent uses a DIFFERENT family than the planner on purpose, so the
#   "examiner" (spec) doesn't share the "student" (planner)'s blind spots.
#   Flash → cheap classification (process/dimension).
def _role_model(role: str, default: str) -> str:
    """Return the model for a role, allowing env overrides without code edits."""
    return os.environ.get(f"{role.upper()}_MODEL", default).strip() or default


AGENT_MODELS: dict[str, str] = {
    "planner":            _role_model("planner", "claude-sonnet-4-20250514"),
    "inspector":          _role_model("inspector", "claude-sonnet-4-20250514"),
    "intent":             _role_model("intent", "gemini-3.1-pro-preview"),
    "vision":             _role_model("vision", "gemini-3.1-pro-preview"),
    "reviewer":           _role_model("reviewer", "gemini-3.1-pro-preview"),
    "process_detector":   _role_model("process_detector", "gemini-3.5-flash"),
    "dimension_extractor": _role_model("dimension_extractor", "gemini-3.5-flash"),
}

# ── Failover preference (used when a role's primary model is unavailable) ────
FALLBACK_ORDER = ["anthropic", "google"]

# Default model per provider for fallback (max-capability stable picks).
PROVIDER_DEFAULT_MODEL = {
    "anthropic": "claude-sonnet-4-20250514",
    "google":    "gemini-3.1-pro-preview",
}


def provider_of(model: str) -> str | None:
    """Return the provider name owning `model` (by substring match), or None."""
    for name, spec in PROVIDERS.items():
        if spec["match"] in model:
            return name
    return None


def available(provider: str) -> bool:
    """True if the provider's API key is present in the environment."""
    env = PROVIDERS.get(provider, {}).get("key_env")
    return bool(env and os.environ.get(env, "").strip())


def fallback_model(role: str) -> str | None:
    """Pick a fallback model for `role`: the first provider in FALLBACK_ORDER
    that (a) differs from the role's primary provider and (b) has a key set."""
    primary = AGENT_MODELS.get(role, "")
    primary_provider = provider_of(primary)
    for prov in FALLBACK_ORDER:
        if prov != primary_provider and available(prov):
            return PROVIDER_DEFAULT_MODEL.get(prov)
    return None
