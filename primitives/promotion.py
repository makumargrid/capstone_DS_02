"""
primitives/promotion.py — Promotion pipeline for custom geometry.

Lifecycle: capture → property-test → approve → register.

GATES:
  1. Property-test battery: N random valid params → build → invariants pass
  2. Human approval gate (caller-provided)
  3. Registry loud-guard: validates on next import

CALLED BY: pipeline.py or interactive tools after a custom node is approved.
"""
from __future__ import annotations
import os
import json
import shutil
import yaml
import random
import logging

logger = logging.getLogger("promotion")


def _root_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def capture_candidate(type_name: str, node_ir: dict, source_run: str = "") -> str:
    """Capture an approved custom node as a candidate template.

    Saves the candidate to config/templates/<type_name>.yaml.
    Returns the path to the saved template.
    """
    templates_dir = os.path.join(_root_dir(), "config", "templates")
    os.makedirs(templates_dir, exist_ok=True)

    candidate = {
        "type": type_name,
        "display_name": node_ir.get("display_name", type_name),
        "builder": node_ir.get("builder", f"build_{type_name}"),
        "param_model": node_ir.get("param_model", f"{type_name.title()}Params"),
        "forgecad": None,
        "checks": node_ir.get("checks", []),
        "params": node_ir.get("params", {}),
        "source_run": source_run,
        "status": "candidate",
    }

    path = os.path.join(templates_dir, f"{type_name}.yaml")
    with open(path, "w") as f:
        yaml.dump(candidate, f)

    logger.info(f"[PROMOTION] Captured candidate '{type_name}' at {path}")
    return path


def run_property_tests(type_name: str, num_samples: int = 10) -> dict:
    """Run property tests on a candidate template.

    Generates N random valid param sets, builds each with the builder,
    runs the full invariant battery, and reports pass/fail.

    Returns {passed: bool, total: int, failures: list, results: list}
    """
    from primitives.registry import LEAF_BUILDERS
    from primitives.compiler import _build_leaf
    from verification.invariants import run_invariants

    # Try to find the candidate in LEAF_BUILDERS already (if just promoted),
    # then try config/templates/ for candidate-only.
    template_dir = os.path.join(_root_dir(), "config", "templates")
    template_path = os.path.join(template_dir, f"{type_name}.yaml")
    if not os.path.isfile(template_path):
        # Not in templates but might be already registered
        if type_name in LEAF_BUILDERS:
            return _run_tests_on_registered(type_name, num_samples)
        return {"passed": False, "total": 0, "failures": [f"Template not found: {template_path}"], "results": []}

    with open(template_path) as f:
        candidate = yaml.safe_load(f)

    builder_name = candidate.get("builder", "")
    param_model_name = candidate.get("param_model", "")
    params_spec = candidate.get("params", {})

    # Try to resolve builder and param model
    try:
        from primitives.params import PARAM_MODELS
        if type_name not in PARAM_MODELS and param_model_name not in PARAM_MODELS:
            return {"passed": False, "total": 0,
                    "failures": [f"Param model '{param_model_name}' not found in PARAM_MODELS"],
                    "results": []}
        model = PARAM_MODELS.get(type_name) or PARAM_MODELS.get(param_model_name)
    except Exception as e:
        return {"passed": False, "total": 0, "failures": [f"Failed to resolve param model: {e}"], "results": []}

    results = []
    failures = []

    for i in range(num_samples):
        try:
            # Generate random valid params
            params = _generate_random_params(model, params_spec)
            # Build the solid
            solid = _build_leaf(type_name, params, {})
            # Run invariants
            inv_checks = run_invariants({"features": [], "envelope": {"x_mm": 100, "y_mm": 100, "z_mm": 100, "tolerance_mm": 10}},
                                        solid, [], min_wall_mm=0.5)
            failed = [c for c in inv_checks if not c["passed"]]
            if failed:
                failures.append({
                    "sample": i + 1,
                    "params": {k: round(v, 2) if isinstance(v, float) else v for k, v in params.items()},
                    "failed_checks": [f"{c['node']}.{c['claim']}" for c in failed],
                })
            results.append({"sample": i + 1, "passed": not failed, "invariant_count": len(inv_checks)})
        except Exception as e:
            failures.append({"sample": i + 1, "error": str(e)})
            results.append({"sample": i + 1, "passed": False, "error": str(e)})

    return {
        "passed": not failures,
        "total": num_samples,
        "passed_count": num_samples - len(failures),
        "failures": failures,
        "results": results,
    }


def promote_primitive(type_name: str) -> dict:
    """Promote a candidate from config/templates/ to config/primitives/.

    1. Moves template YAML to primitives directory
    2. Adds a params field description (the template YAML already has it)
    3. Clears the config loader cache so registry picks it up on next import
    4. Validates the registry loads it correctly

    Returns {success: bool, type_name: str, message: str}
    """
    root = _root_dir()
    template_path = os.path.join(root, "config", "templates", f"{type_name}.yaml")
    primitive_path = os.path.join(root, "config", "primitives", f"{type_name}.yaml")

    if not os.path.isfile(template_path):
        return {"success": False, "type_name": type_name, "message": f"Template not found: {template_path}"}

    # Read the template
    with open(template_path) as f:
        candidate = yaml.safe_load(f)

    # Update status
    candidate["status"] = "promoted"

    # Write to primitives/
    with open(primitive_path, "w") as f:
        yaml.dump(candidate, f)

    # Remove from templates/
    os.remove(template_path)

    # Clear config loader cache (lru_cache uses __wrapped__ for cache access)
    from core.config_loader import load_config, load_all_primitive_configs
    try:
        load_config.__wrapped__.cache_clear()
    except Exception:
        pass
    try:
        load_all_primitive_configs.__wrapped__.cache_clear()
    except Exception:
        pass

    # Validate registry picks it up
    try:
        import importlib
        import primitives.registry as _reg
        importlib.reload(_reg)
        if type_name in _reg.LEAF_BUILDERS:
            logger.info(f"[PROMOTION] '{type_name}' promoted and registered successfully")
            return {"success": True, "type_name": type_name,
                    "message": f"'{type_name}' promoted to config/primitives/ and registered"}
        else:
            return {"success": False, "type_name": type_name,
                    "message": f"'{type_name}' YAML written but registry did not pick it up"}
    except Exception as e:
        return {"success": False, "type_name": type_name,
                "message": f"Registry validation failed: {e}"}


def reject_candidate(type_name: str) -> dict:
    """Remove a candidate from config/templates/."""
    template_path = os.path.join(_root_dir(), "config", "templates", f"{type_name}.yaml")
    if os.path.isfile(template_path):
        os.remove(template_path)
        logger.info(f"[PROMOTION] Rejected candidate '{type_name}' — removed from templates")
        return {"success": True, "type_name": type_name, "message": f"Removed '{type_name}'"}
    return {"success": False, "type_name": type_name, "message": f"No template found for '{type_name}'"}


def _generate_random_params(model_class, params_spec: dict) -> dict:
    """Generate random valid params for a param model."""
    params = {}
    fields = params_spec.get("fields", {})
    if not fields:
        # Try to infer from model class
        from pydantic.fields import FieldInfo
        for name, field_info in model_class.model_fields.items():
            if name == "at":
                params[name] = [random.uniform(-5, 5), random.uniform(-5, 5), random.uniform(0, 5)]
            elif name in ("operation",):
                params[name] = "extrude"
            elif name in ("sketch",):
                params[name] = {"type": "circle", "params": {"radius": random.uniform(1, 20)}}
            elif hasattr(field_info, 'gt') and field_info.gt is not None:
                gt = float(field_info.gt) if isinstance(field_info.gt, (int, float)) else 0.5
                params[name] = round(random.uniform(gt, gt * 50), 2)
            else:
                params[name] = round(random.uniform(0.5, 25), 2)
    else:
        for name, spec in fields.items():
            if spec.get("type") == "dict":
                params[name] = {"type": "circle", "params": {"radius": random.uniform(1, 20)}}
            elif spec.get("type") == "str":
                params[name] = "extrude"
            else:
                gt = float(spec.get("gt", 0.5))
                params[name] = round(random.uniform(gt, gt * 50), 2)
    return params


def _run_tests_on_registered(type_name: str, num_samples: int) -> dict:
    """Run property tests on an already-registered primitive (like profile)."""
    from primitives.registry import LEAF_BUILDERS
    from primitives.params import PARAM_MODELS
    from verification.invariants import run_invariants

    if type_name not in LEAF_BUILDERS or type_name not in PARAM_MODELS:
        return {"passed": False, "total": 0, "failures": ["Not registered"], "results": []}

    model = PARAM_MODELS[type_name]
    builder_fn, _ = LEAF_BUILDERS[type_name]
    results = []
    failures = []

    for i in range(num_samples):
        try:
            params = _generate_random_params(model, {})
            solid = builder_fn(model.model_validate(params), {})
            if not solid.isValid():
                failures.append({"sample": i + 1, "error": "invalid solid"})
                results.append({"sample": i + 1, "passed": False, "error": "invalid solid"})
                continue
            inv_checks = run_invariants({"features": [], "envelope": {"x_mm": 500, "y_mm": 500, "z_mm": 500, "tolerance_mm": 50}},
                                        solid, [], min_wall_mm=0.1)
            failed = [c for c in inv_checks if not c["passed"]]
            if failed:
                failures.append({
                    "sample": i + 1,
                    "failed_checks": [f"{c['node']}.{c['claim']}" for c in failed],
                })
            results.append({"sample": i + 1, "passed": not failed})
        except Exception as e:
            failures.append({"sample": i + 1, "error": str(e)})
            results.append({"sample": i + 1, "passed": False, "error": str(e)})

    return {
        "passed": not failures,
        "total": num_samples,
        "passed_count": num_samples - len(failures),
        "failures": failures,
        "results": results,
    }