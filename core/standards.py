"""
core/standards.py — engineering standards lookup for dimension grounding.

When the Spec or planner encounters an ambiguous dimension (e.g., "hole for M6 bolt"),
this module looks up the standard value from config/standards/ and returns it with
a citation. Standards inform generation, never override verification.

LOOKUP FUNCTIONS:
  lookup_clearance_hole(bolt_size: str, fit: str = "medium") -> dict | None
  lookup_metric_bolt(bolt_size: str) -> dict | None
  lookup_fit(fit_name: str) -> dict | None
  lookup_min_wall(material: str) -> dict | None
  lookup_standard(query: str) -> dict | None   — general-purpose
"""
from __future__ import annotations
import re
from core.config_loader import load_config


def _yaml(path):
    return load_config(f"standards/{path}")


def lookup_clearance_hole(bolt_size: str, fit: str = "medium") -> dict | None:
    """Look up a clearance hole diameter for a metric bolt size.
    Returns {value: float, source: str} or None if not found.
    """
    data = _yaml("fasteners/clearance_holes.yaml")
    entry = data.get(bolt_size.upper())
    if entry is None:
        return None
    dia = entry.get(fit)
    if dia is None:
        dia = entry.get("medium", 6.6)  # fallback
    return {"value": float(dia), "source": entry.get("source", "ISO 273")}


def lookup_metric_bolt(bolt_size: str) -> dict | None:
    """Look up metric bolt dimensions. Returns dict with major_diameter, pitch, etc."""
    data = _yaml("fasteners/metric_bolts.yaml")
    entry = data.get(bolt_size.upper())
    if entry is None:
        return None
    return {
        "major_diameter": entry.get("major_diameter"),
        "pitch": entry.get("pitch"),
        "head_diameter": entry.get("head_diameter"),
        "head_height": entry.get("head_height"),
        "source": "ISO 4017 / ISO 4762",
    }


def lookup_fit(fit_name: str) -> dict | None:
    """Look up an ISO 286 fit combination. Returns {description, clearance, source}."""
    data = _yaml("fits/iso_286_tolerances.yaml")
    fits = data.get("fits", {})
    return fits.get(fit_name)


def lookup_min_wall(material: str) -> dict | None:
    """Look up minimum wall thickness for a material. Returns {value, source}."""
    data = _yaml("material_min_walls.yaml")
    entry = data.get(material.lower())
    if entry is None:
        return None
    return {"value": float(entry.get("min_wall", 1.0)), "source": entry.get("source", "Engineering guidelines")}


def lookup_standard(query: str) -> dict | None:
    """General-purpose standards lookup from a natural-language query.
    Parses queries like 'M6 bolt clearance hole', 'M8 bolt', 'H7/h6 fit'.

    Returns {value, source, category, key} or None.
    """
    q = query.lower().strip()

    # Pattern: "M6 bolt clearance hole" or "clearance hole for M6"
    m = re.search(r'M(\d+)', q.upper())
    bolt_size = m.group(0) if m else None

    if "clearance" in q and bolt_size:
        result = lookup_clearance_hole(bolt_size)
        if result:
            return {**result, "category": "fasteners", "key": bolt_size}
    elif bolt_size and ("bolt" in q or "screw" in q or "thread" in q):
        result = lookup_metric_bolt(bolt_size)
        if result:
            dia = result["major_diameter"]
            return {"value": dia, "source": result["source"], "category": "fasteners", "key": bolt_size}
    elif "fit" in q or "h7" in q.lower() or "h6" in q.lower():
        for fit_key in ("H7_h6", "H7_g6", "H8_f7"):
            if fit_key.lower().replace("_", "/").replace("-", "") in q.lower().replace("_", "/").replace("-", ""):
                result = lookup_fit(fit_key)
                if result:
                    return {"value": result["clearance"], "source": result["source"], "category": "fits", "key": fit_key}
    elif "wall" in q or "thickness" in q or "material" in q:
        # Try to extract material from query
        for mat in ("abs", "pla", "petg", "nylon", "aluminum", "steel", "stainless", "titanium"):
            if mat in q:
                result = lookup_min_wall(mat)
                if result:
                    return {**result, "category": "material", "key": mat}

    return None