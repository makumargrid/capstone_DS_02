"""
core/process_detector.py — manufacturing-process detection + DFM profile load.

WHAT:
    detect_process(prompt) → process key (FDM/SLA/SLS/CNC/INJECTION_MOLDING/
        CASTING) via Stage-1 keyword scan, Stage-2 LLM fallback, else default.
    load_profile(key)      → that process's DFM profile (min_wall_mm, tolerance,
        rules) from knowledge_base/manufacturing_profiles.json.

CALLED BY: pipeline.py (to pick the process + min wall for L2 checks).
CALLS:     core/llm_client.call_llm (Stage-2), core/model_config.get_model_name,
           core/logger; reads knowledge_base/manufacturing_profiles.json.
"""
from __future__ import annotations
import json
import os
from typing import Optional

from .logger import get_agent_logger

logger = get_agent_logger()

_KB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "knowledge_base", "manufacturing_profiles.json")
_profiles: Optional[dict] = None


def _load_kb() -> dict:
    global _profiles
    if _profiles is None:
        with open(_KB_PATH) as f:
            _profiles = json.load(f)
    return _profiles


def detect_process(prompt: str) -> str:
    """Detect the manufacturing process: keyword scan → LLM fallback → default."""
    kb = _load_kb()
    pl = prompt.lower()

    scores = {k: sum(1 for kw in p.get("keywords", []) if kw.lower() in pl)
              for k, p in kb.items() if not k.startswith("_")}
    scores = {k: v for k, v in scores.items() if v > 0}
    if scores:
        best = max(scores, key=scores.get)
        logger.info(f"[PROCESS_DETECT] keyword match → '{best}' {scores}")
        return best

    logger.info("[PROCESS_DETECT] no keyword match — LLM classify")
    try:
        from .llm_client import call_llm
        from .model_config import get_model_name
        valid = [k for k in kb if not k.startswith("_")]
        prompt_txt = (
            f"You are a manufacturing process classifier.\nUser prompt: \"{prompt}\"\n"
            f"Choose exactly ONE from: {', '.join(valid)}.\n"
            f"3D print/FFF/PLA/ABS→FDM; resin/SLA/DLP→SLA; sintering/powder→SLS; "
            f"CNC/machining/metal/aluminum→CNC; injection/tooling→INJECTION_MOLDING; "
            f"casting/foundry→CASTING; none→FDM.\nReply with ONLY the key.")
        result = call_llm(get_model_name("process_detector"), prompt_txt).strip().upper()
        result = result.replace("-", "_").replace(" ", "_")
        if result in valid:
            logger.info(f"[PROCESS_DETECT] LLM → '{result}'")
            return result
        logger.warning(f"[PROCESS_DETECT] unrecognized '{result}', using default")
    except Exception as e:
        logger.warning(f"[PROCESS_DETECT] LLM fallback failed ({e}), using default")

    default = kb.get("_default", "FDM")
    logger.info(f"[PROCESS_DETECT] default process: '{default}'")
    return default


def load_profile(process_key: str) -> dict:
    """Load a process DFM profile; falls back to FDM if the key is unknown."""
    kb = _load_kb()
    if process_key not in kb:
        logger.warning(f"[PROCESS_DETECT] unknown '{process_key}', using FDM")
        process_key = "FDM"
    profile = kb[process_key].copy()
    profile["process_key"] = process_key
    logger.info(f"[PROCESS_DETECT] profile: {profile['full_name']} "
                f"(min_wall={profile['min_wall_mm']}mm)")
    return profile
