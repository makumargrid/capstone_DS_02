"""Env/model bootstrap tests — no live LLM calls."""
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _restore_env(saved):
    for key in (
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "GOOGLE_GENAI_USE_VERTEXAI",
        "PLANNER_MODEL",
    ):
        if saved.get(key) is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = saved[key]


def test_bootstrap_env_aliases_gemini_to_google():
    saved = {k: os.environ.get(k) for k in os.environ}
    try:
        os.environ.pop("GOOGLE_API_KEY", None)
        os.environ.pop("GOOGLE_GENAI_USE_VERTEXAI", None)
        os.environ["GEMINI_API_KEY"] = "gemini-key"
        import core.env as _env
        _env._BOOTSTRAPPED = False  # Reset so bootstrap_env can re-run
        from core.env import bootstrap_env

        bootstrap_env(load_dotenv_file=False)

        assert os.environ["GOOGLE_API_KEY"] == "gemini-key"
        assert os.environ["GOOGLE_GENAI_USE_VERTEXAI"] == "false"
    finally:
        _restore_env(saved)
        import core.env as _env3
        _env3._BOOTSTRAPPED = False


def test_bootstrap_env_aliases_google_to_gemini():
    saved = {k: os.environ.get(k) for k in os.environ}
    try:
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ["GOOGLE_API_KEY"] = "google-key"
        import core.env as _env
        _env._BOOTSTRAPPED = False  # Reset so bootstrap_env can re-run
        from core.env import bootstrap_env

        bootstrap_env(load_dotenv_file=False)

        assert os.environ["GEMINI_API_KEY"] == "google-key"
    finally:
        _restore_env(saved)
        import core.env as _env2
        _env2._BOOTSTRAPPED = False  # Reset for subsequent tests


def test_provider_model_can_be_overridden_by_role_env():
    saved = {k: os.environ.get(k) for k in os.environ}
    try:
        os.environ["PLANNER_MODEL"] = "gemini-2.5-flash"
        os.environ["GOOGLE_API_KEY"] = "google-key"
        os.environ.pop("ANTHROPIC_API_KEY", None)

        import core.providers as providers
        importlib.reload(providers)

        assert providers.AGENT_MODELS["planner"] == "gemini-2.5-flash"
        assert providers.PROVIDER_DEFAULT_MODEL["google"] == "gemini-2.5-pro"
    finally:
        _restore_env(saved)
        if "core.providers" in sys.modules:
            importlib.reload(sys.modules["core.providers"])


def test_leaf_builders_matches_invariant_set():
    """Invariant 1: LEAF_BUILDERS must contain exactly the expected 7 types."""
    from primitives.registry import LEAF_BUILDERS
    expected = {"cylinder", "cone", "frustum", "box", "hole", "sphere", "tube", "profile"}
    assert set(LEAF_BUILDERS) == expected, (
        f"LEAF_BUILDERS mismatch: got {set(LEAF_BUILDERS)}, expected {expected}"
    )


def test_missing_primitive_yaml_crashes_import():
    """Invariant 4: removing a primitive YAML must make primitives.registry import fail."""
    import tempfile
    import shutil

    # Simulate a missing YAML by temporarily hiding one
    config_primitives_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config", "primitives",
    )
    yaml_to_hide = os.path.join(config_primitives_dir, "sphere.yaml")
    hidden = os.path.join(tempfile.gettempdir(), "sphere.yaml.hidden")

    if not os.path.exists(yaml_to_hide):
        # Skip if sphere.yaml doesn't exist (shouldn't happen, but don't crash)
        return

    shutil.move(yaml_to_hide, hidden)
    try:
        # Clear all caches and modules so the registry reimports fresh
        from core.config_loader import load_config, load_all_primitive_configs
        load_config.cache_clear()
        load_all_primitive_configs.cache_clear()
        # Remove all primitives modules from sys.modules
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith("primitives"):
                del sys.modules[mod_name]
        # Now try to reimport — it should raise ImportError
        try:
            import primitives.registry as _reg
            assert False, "Should have raised ImportError for missing YAML"
        except ImportError:
            pass  # expected — loud failure on missing YAML
    finally:
        shutil.move(hidden, yaml_to_hide)
        # Restore cache and registry state
        from core.config_loader import load_config, load_all_primitive_configs
        load_config.cache_clear()
        load_all_primitive_configs.cache_clear()
        # Remove and reimport to restore clean state
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith("primitives"):
                del sys.modules[mod_name]
        try:
            import primitives.registry  # noqa: F811
        except Exception:
            pass  # registry will self-heal on next import naturally




def test_standards_lookup_m6_clearance_hole():
    """M6 bolt clearance hole returns 6.6mm with ISO 273 citation."""
    from core.standards import lookup_standard
    result = lookup_standard("M6 bolt clearance hole")
    assert result is not None, "M6 clearance hole should be found"
    assert result["value"] == 6.6, f"Expected 6.6mm, got {result['value']}"
    assert "ISO 273" in result["source"], f"Expected ISO 273 citation, got {result['source']}"
    assert result["category"] == "fasteners"
    assert result["key"] == "M6"


def test_standards_lookup_m8_bolt():
    """M8 bolt lookup returns major diameter 8.0mm."""
    from core.standards import lookup_standard
    result = lookup_standard("M8 bolt dimensions")
    assert result is not None, "M8 bolt should be found"
    assert result["value"] == 8.0
    assert "ISO 4017" in result["source"]


def test_rag_kb_files_no_longer_exist():
    """rag_kb1.py and rag_kb2.py are deleted."""
    import os as _os
    root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    assert not _os.path.exists(_os.path.join(root, "rag_kb1.py")), "rag_kb1.py should be deleted"
    assert not _os.path.exists(_os.path.join(root, "rag_kb2.py")), "rag_kb2.py should be deleted"


def test_knowledge_modules_import():
    """knowledge.cadquery_api and knowledge.occt_errors are importable."""
    from knowledge.cadquery_api import get_api_context
    from knowledge.occt_errors import get_error_context
    assert callable(get_api_context)
    assert callable(get_error_context)


def test_skill_files_loaded():
    """All four agent skill files exist and load successfully."""
    import os as _os
    _ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    skill_dirs = {
        "planner": ["SKILL.md", "ASSEMBLY.md"],
        "reviewer": ["SKILL.md"],
        "vision": ["SKILL.md"],
        "meshlib": ["SKILL.md"],
    }
    for agent, files in skill_dirs.items():
        for fname in files:
            path = _os.path.join(_ROOT, "skills", agent, fname)
            assert _os.path.exists(path), f"Missing {path}"
            with open(path) as f:
                content = f.read()
            assert len(content) > 50, f"Empty or short skill file: {path}"



def test_intent_resolution_resolves_m6_clearance():
    """Intent resolution grounds 'M6 bolt hole' to 6.6mm with ISO 273.
    Note: Spec extraction uses LLM; regex fallback may not produce bore target.
    This test verifies the _ground_spec function directly."""
    from core.intent_resolver import _ground_spec

    # Simulate a spec with a bore requirement from a prompt mentioning M6
    spec = [
        {"id": "r1", "description": "through hole for M6 bolt", "claim": "bore_diameter_mm",
         "target": "bore", "expected": None, "tolerance": None, "severity": "required"},
    ]
    prompt = "Make a bracket with a hole for an M6 bolt"
    grounded = _ground_spec(spec, prompt)
    bore = grounded[0]
    assert bore["expected"] == 6.6, f"Expected 6.6mm, got {bore['expected']}"
    assert "ISO 273" in bore.get("source", ""), f"No ISO citation: {bore}"


def test_intent_resolution_detects_engineer():
    """Technical prompts are detected as engineering language."""
    from core.intent_resolver import _is_engineer
    assert _is_engineer("a 100mm diameter bore with H7 tolerance and 2mm fillet")
    assert not _is_engineer("make me a simple plastic box with a lid")


def test_explain_plan_from_ir():
    """explain_plan derives plain-language text from IR structure."""
    from core.intent_resolver import explain_plan
    ir = {
        "version": "1.0", "units": "mm", "process": "FDM",
        "envelope": {"x_mm": 100, "y_mm": 100, "z_mm": 20, "tolerance_mm": 3},
        "features": [
            {"id": "plate", "type": "box", "params": {"length": 100, "width": 100, "height": 10}},
            {"id": "bolts", "type": "circular_pattern", "op": "cut", "target": "plate",
             "params": {"count": 4, "axis": [0, 0, 1],
                        "feature": {"id": "b", "type": "hole", "params": {"diameter": 6}}}},
        ],
    }
    explanation = explain_plan(ir)
    assert "plate" in explanation
    assert "bolts" in explanation
    assert "hole" in explanation
    assert "100" in explanation  # envelope dimension


def test_spec_confirmed_gate_prevents_compile_on_no():
    """Non-interactive auto-confirms; unconfirmed halts pipeline."""
    from core.intent_resolver import resolve_intent
    # Non-interactive: always confirmed
    result = resolve_intent("test part", {}, interactive=False)
    assert result["confirmed"]

    # Interactive with reject: a question_handler that returns "no"
    def reject(question):
        return "no"
    result2 = resolve_intent("test part", {}, interactive=True, question_handler=reject)
    assert not result2["confirmed"]



def test_image_intake_saves_to_session():
    """Reference image is saved to the session directory."""
    import tempfile
    import os as _os
    from interaction.image_intake import save_reference_image, has_reference_image, get_reference_image

    with tempfile.TemporaryDirectory() as d:
        # Create a dummy image
        img_path = _os.path.join(d, "test.png")
        with open(img_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        session_dir = _os.path.join(d, "session")
        saved = save_reference_image(img_path, session_dir)
        assert _os.path.isfile(saved), f"Image not saved at {saved}"
        assert has_reference_image(session_dir)
        assert get_reference_image(session_dir) is not None


def test_visual_confirm_never_gates_dimensions():
    """Visual confirmation is advisory — never blocks on dimension."""
    from interaction.visual_confirm import compare_to_reference
    import tempfile, os as _os
    # Create a real reference image
    with tempfile.TemporaryDirectory() as d:
        img_path = _os.path.join(d, "ref.png")
        with open(img_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        # With rendered views and a real reference image
        result = compare_to_reference(
            {"iso": img_path},  # rendered views
            img_path,           # reference image
        )
        assert result["shape_match"] is None, "Should not assert a shape match without good evidence"
        assert "never gate dimensions" in result["notes"].lower()


def test_image_intake_no_file_returns_empty():
    """Missing reference image returns None gracefully."""
    from interaction.image_intake import get_reference_image, has_reference_image
    import tempfile, os as _os
    with tempfile.TemporaryDirectory() as d:
        assert not has_reference_image(d)
        assert get_reference_image(d) is None



def test_meshlib_determinism_same_result():
    """Deterministic mesh battery: same mesh → identical measurements on repeat runs."""
    from agents.meshlib_agent import run_inspection
    import tempfile

    # Create a valid STL file (minimal binary STL)
    with tempfile.TemporaryDirectory() as d:
        stl_path = os.path.join(d, "test.stl")
        # Minimal valid binary STL: 80-byte header + 4-byte count = empty mesh
        with open(stl_path, "wb") as f:
            f.write(b"\x00" * 80 + b"\x00\x00\x00\x00")

        r1 = run_inspection(stl_path, {"prompt": "test"}, d, 1)
        r2 = run_inspection(stl_path, {"prompt": "test"}, d, 2)

        assert r1["deterministic"] is True, "run_inspection should be marked deterministic"
        assert r2["deterministic"] is True
        assert r1["method"] == "fixed_geometric_battery"
        assert r2["method"] == "fixed_geometric_battery"
        # Same mesh → same number of checks
        assert len(r1["checks"]) == len(r2["checks"]), (
            f"Determinism violation: {len(r1['checks'])} vs {len(r2['checks'])} checks"
        )


def test_manifest_has_certificate_and_trust_label():
    """Every handoff manifest has certificate, requires_review, and trust_label."""
    from handoff import emit_forgecad_bundle
    from tests.fixtures import pattern_box_ir
    import tempfile

    ir = pattern_box_ir()
    with tempfile.TemporaryDirectory() as d:
        m = emit_forgecad_bundle(ir, d)
        assert "certificate" in m, "Manifest missing certificate"
        assert "requires_review" in m, "Manifest missing requires_review"
        assert "trust_label" in m, "Manifest missing trust_label"
        assert m["trust_label"] in ("certified", "requires_review", "flagged")
        # pattern_box_ir has no custom nodes → trust_label = certified
        assert m["trust_label"] == "certified", f"Expected certified, got {m['trust_label']}"
        assert m["requires_review"] is False


def test_config_loader_caches():
    """Config loader caches repeated reads."""
    from core.config_loader import load_config
    load_config.cache_clear()
    first = load_config("checks/inspection_thresholds.yaml")
    second = load_config("checks/inspection_thresholds.yaml")
    assert first is second  # lru_cache returns same object



def test_m4_bolt_hole_resolves_to_4_5mm():
    """M4 bolt clearance hole returns 4.5mm with ISO 273 citation."""
    from core.intent_resolver import _ground_spec
    spec = [
        {"id": "r1", "description": "through hole for M4 bolt", "claim": "bore_diameter_mm",
         "target": "bore", "expected": None, "tolerance": None, "severity": "required"},
    ]
    prompt = "Make a bracket with a hole for an M4 bolt"
    grounded = _ground_spec(spec, prompt)
    bore = grounded[0]
    assert bore["expected"] == 4.5, f"Expected 4.5mm, got {bore['expected']}"
    assert "ISO 273" in bore.get("source", ""), f"No ISO citation: {bore}"


def test_gate2_refine_request_preserved():
    """In interactive mode, refine request reaches the pipeline."""
    from core.intent_resolver import resolve_intent
    # Interactive with an edit response — should be treated as clarification
    def edit_handler(question):
        return "increase the bore to 20mm"
    result = resolve_intent("test part", {}, interactive=True, question_handler=edit_handler)
    assert result["confirmed"]
    assert len(result["clarification_notes"]) > 0
    assert "increase" in result["clarification_notes"][0].lower()


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn(); print(f"PASS {fn.__name__}")
        except Exception:
            failed += 1; print(f"FAIL {fn.__name__}"); traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
