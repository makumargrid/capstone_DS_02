# Repository Guidelines

## Project Structure & Module Organization
- `pipeline.py`: main orchestrator — intent resolution, IR planning, compilation, L2 inspection, L3 vision, reviewer routing, ForgeCAD handoff.
- `core/`: runtime modules (`env.py`, `providers.py`, `llm_client.py`, `process_detector.py`, `sandbox.py`, `spec.py`, `intent_resolver.py`, `standards.py`, `config_loader.py`).
- `primitives/`: parametric builders (`builders.py`), compiler (`compiler.py`), registry (`registry.py`), anchoring (`anchoring.py`), models (`params.py`).
- `verification/`: deterministic checks — `solid_inspector.py` (L2), `invariants.py` (universal), `dfm.py` (DFM), `renderer.py` (headless views).
- `config/`: YAML-driven configuration — `primitives/` (one YAML per primitive type), `process/manufacturing_profiles.json` (DFM thresholds), `inspection_thresholds.yaml`.
- `skills/`: agent skill files — `planner/SKILL.md`, `vision/SKILL.md`, `reviewer/SKILL.md`.
- `knowledge/`: knowledge corpus — `process_knowledge.md`, `primitive_examples.md`.
- `agents/`: ADK agents (`planner_agent`, `reviewer_agent`, `vision_agent`) and tooling.
- `handoff/`: ForgeCAD bundle emitter (`forgecad_emit.py`) + interactive viewer.
- `outputs/run_YYYYMMDD_HHMMSS/`: run artifacts and audit trail.

## Build, Test, and Development Commands
- `docker build -t agentic-cad-pipeline .`: build the recommended runtime image.
- `docker run --env-file .env -v "$(pwd)/outputs:/app/outputs" agentic-cad-pipeline python pipeline.py "<prompt>"`: run full pipeline in container.
- `python pipeline.py "<prompt>"` or `python pipeline.py --interactive "<prompt>"`: local execution (requires CadQuery, MeshLib, ADK, provider SDKs).
- `python tests/test_acceptance_groundtruth.py`: frozen ground-truth oracle (9 cases).
- `python tests/test_env.py`: env bootstrap, key aliasing, registry guard, intent resolution.
- `python tests/test_solid_inspector.py`: L2 deterministic checker.
- `python tests/test_primitives.py`: all 8 primitives + compiler + export.

## Coding Style & Naming Conventions
- Python, 4-space indentation, PEP 8 style, and type hints where practical.
- Naming: `snake_case` for functions/variables, `UPPER_CASE` for constants (for example, `MAX_OUTER`).
- Keep phase logic explicit and logged; preserve deterministic checks before AI review.
- Do not break reviewer information asymmetry: reviewer inputs must exclude raw generated CAD code.

## Verdict Contract
- `geometrically_valid` (bool): driven ONLY by structural/intent checks (single_solid, envelope, feature_contributes, hole_edge_clearance, bore, thickness, fillet/chamfer).
- `manufacturable` (bool): driven ONLY by DFM checks for the active process (overhang, bridge_span, draft, min_hole, min_feature).
- `valid` (bool): backwards-compat == `geometrically_valid`.
- Every check tagged `severity: "blocking" | "dfm"`.
- Certificate reports BOTH flags; never claims certified when `manufacturable=False`.

## Testing Guidelines
- Run the frozen ground-truth oracle after every change: `python tests/test_acceptance_groundtruth.py`.
- For each change, run the full test suite: all `tests/test_*.py` files.
- When touching geometry checks, verify against the oracle's independent ground-truth assertions.
- Never weaken an oracle assertion to make it pass — fix the code instead.

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
- Custom code runs in a sandboxed subprocess (`core/sandbox.py`) with network blocked, credentials stripped, and wall-clock timeout.
