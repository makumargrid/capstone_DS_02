"""
core/ — shared infrastructure used by every agent and stage.

Modules:
  providers.py        THE single provider switch-point (swap models here).
  model_config.py     model resolution + ADK registry patch + safe_parse_json.
  llm_client.py       direct (non-ADK) LLM call with failover.
  logger.py           per-run logging.
  process_detector.py manufacturing process + DFM profile selection.
"""

from . import _quiet  # noqa: F401  (installs event-loop noise suppressor)
