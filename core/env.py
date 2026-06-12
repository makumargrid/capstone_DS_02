"""
core/env.py — process-wide environment bootstrap for model providers.

WHAT: load the repository .env once, normalize Gemini key aliases for both ADK
      and direct google-genai calls, and default Gemini to the Developer API.
CALLS: python-dotenv when installed; os.environ only otherwise.
"""
from __future__ import annotations

import os
from pathlib import Path

_BOOTSTRAPPED = False


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def bootstrap_env(load_dotenv_file: bool = True) -> None:
    """Load .env and normalize provider env names without exposing secrets."""
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return 
    if load_dotenv_file:
        try:
            from dotenv import load_dotenv
            # override=True: .env file ALWAYS takes priority over shell env vars.
            # This ensures the project .env is the single source of truth, preventing
            # stale terminal `export` values from blocking fresh .env keys.
            load_dotenv(_repo_root() / ".env", override=True)
        except Exception:
            pass

    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "false")

    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    google_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if gemini_key and not google_key:
        os.environ["GOOGLE_API_KEY"] = gemini_key
    elif google_key and not gemini_key:
        os.environ["GEMINI_API_KEY"] = google_key

    _BOOTSTRAPPED = True


def provider_presence() -> dict[str, bool]:
    """Secret-safe presence summary for diagnostics."""
    bootstrap_env()
    return {
        "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY", "").strip()),
        "google": bool(os.environ.get("GOOGLE_API_KEY", "").strip()
                       or os.environ.get("GEMINI_API_KEY", "").strip()),
    }


def diagnostic_summary() -> str:
    """Return a one-line diagnostic of which providers are available.
    Safe to log — shows presence only, never key values."""
    bootstrap_env()
    present = provider_presence()
    parts = []
    parts.append(f"anthropic={'✓' if present['anthropic'] else '✗'}")
    parts.append(f"google={'✓' if present['google'] else '✗'}")
    return "[ENV] providers: " + " | ".join(parts)

