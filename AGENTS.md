# Repository Guidelines

## Project Structure & Module Organization
- `pipeline.py`: main orchestrator for the 6-phase CAD pipeline (planning, execution, export, static checks, AI inspection, adversarial review).
- `src/`: core runtime modules (`llm.py`, `cad_executor.py`, `mesh_inspector.py`, `process_detector.py`, `model_config.py`, `logger.py`).
- `agents/`: ADK agents (`planner_agent`, `meshlib_agent`, `reviewer_agent`) and sandboxed execution helpers.
- `knowledge_base/manufacturing_profiles.json`: process-specific DFM constraints (FDM, SLA, SLS, CNC, etc.).
- `outputs/run_YYYYMMDD_HHMMSS/`: run artifacts and audit trail (`00_...log` through `07_...verdict.json`).

## Build, Test, and Development Commands
- `docker build -t agentic-cad-pipeline .`: build the recommended runtime image.
- `docker run --env-file .env -v "$(pwd)/outputs:/app/outputs" agentic-cad-pipeline python pipeline.py "<prompt>"`: run full pipeline in container.
- `python pipeline.py "<prompt>"` or `python pipeline.py --interactive "<prompt>"`: local execution.
- `./agents/.agnts/bin/python -m google.adk.cli web --session_service_uri sqlite:///outputs/adk_sessions.db --port 8080 agents`: inspect agent sessions in ADK Web UI.
- `python scratch_test.py`: quick MeshLib binding smoke check.

## Coding Style & Naming Conventions
- Python, 4-space indentation, PEP 8 style, and type hints where practical.
- Naming: `snake_case` for functions/variables, `UPPER_CASE` for constants (for example, `MAX_OUTER_RETRIES`).
- Keep phase logic explicit and logged; preserve deterministic checks before AI review.
- Do not break reviewer information asymmetry: reviewer inputs must exclude raw generated CAD code.

## Testing Guidelines
- No formal `tests/` suite is committed yet; rely on smoke/integration verification.
- For each change, run at least:
  - `python scratch_test.py`
  - one end-to-end pipeline run and confirm expected files in a new `outputs/run_*` directory.
- When touching geometry checks, verify `05_outer*_static_inspection_ground_truth.json` values against the prompt intent.

## Commit & Pull Request Guidelines
- Current history uses short, direct subjects (for example, `Integrate ...`, `Enhance ...`). Continue with imperative, single-line commit titles.
- PRs should include:
  - what changed and why,
  - impacted modules/agents,
  - one sample output path (or log excerpt) proving behavior,
  - screenshots only when UI/ADK session behavior is relevant.

## Security & Configuration Tips
- Keep secrets only in `.env` (`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`); never commit credentials.
- Treat `outputs/` as generated artifacts; avoid committing large run folders unless explicitly needed for debugging.
