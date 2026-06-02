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
        from core.env import bootstrap_env

        bootstrap_env(load_dotenv_file=False)

        assert os.environ["GOOGLE_API_KEY"] == "gemini-key"
        assert os.environ["GOOGLE_GENAI_USE_VERTEXAI"] == "false"
    finally:
        _restore_env(saved)


def test_bootstrap_env_aliases_google_to_gemini():
    saved = {k: os.environ.get(k) for k in os.environ}
    try:
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ["GOOGLE_API_KEY"] = "google-key"
        from core.env import bootstrap_env

        bootstrap_env(load_dotenv_file=False)

        assert os.environ["GEMINI_API_KEY"] == "google-key"
    finally:
        _restore_env(saved)


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
