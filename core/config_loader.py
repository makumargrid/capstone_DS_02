"""
core/config_loader.py — cached YAML/JSON loaders for the config/ tree.

All tunable values (thresholds, primitive metadata, process profiles) live
in config/ and are read through these loaders. Results are cached per-process
(via lru_cache) so repeated calls don't re-read files.

ADD A CONFIG FILE: place it under config/ and call load_config("path/to/file").
"""
from __future__ import annotations
import functools
import json
import os

import yaml

_CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")


@functools.lru_cache(maxsize=64)
def load_config(rel_path: str) -> dict:
    """Load a YAML or JSON file from config/<rel_path>. Results are cached."""
    full = os.path.join(_CONFIG_DIR, rel_path)
    with open(full) as f:
        if full.endswith((".yaml", ".yml")):
            return yaml.safe_load(f)
        return json.load(f)


def load_primitive_config(primitive_type: str) -> dict:
    """Load a single primitive's YAML definition."""
    return load_config(f"primitives/{primitive_type}.yaml")


def load_all_primitive_configs() -> list[dict]:
    """Return all primitive YAML definitions from config/primitives/."""
    primitives_dir = os.path.join(_CONFIG_DIR, "primitives")
    configs = []
    for fname in sorted(os.listdir(primitives_dir)):
        if fname.endswith((".yaml", ".yml")):
            configs.append(load_config(f"primitives/{fname}"))
    return configs


def load_inspection_thresholds() -> dict:
    """Load inspection thresholds from config/checks/inspection_thresholds.yaml."""
    return load_config("checks/inspection_thresholds.yaml")


def load_process_profiles() -> dict:
    """Load manufacturing process profiles."""
    return load_config("process/manufacturing_profiles.json")