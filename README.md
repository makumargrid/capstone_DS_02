# Advanced Agentic CAD Generation & Quality Assurance Pipeline

This repository runs an **IR-centric agentic CAD pipeline**. Instead of
regenerating free-form CadQuery each loop, the planner emits a typed, validated
**Geometry IR** (a parametric feature tree in JSON) that is the single source of
truth for generation, verification, and editing:

1. **Planner Agent** emits a Geometry IR (typed primitives) — tools:
   `list_primitives`, `get_primitive_schema`, `validate_plan`, `ask_user`.
2. **Deterministic compiler** builds the CadQuery solid + per-feature provenance.
3. **L1** schema/reference validation → **L2** solid-level deterministic checks
   against the IR's declared claims (the intent ground truth) → **L3** headless
   multi-view render + Vision Verifier (advisory) → **L4** MeshLib (demoted: only
   for `custom`/mesh-only nodes).
4. **Reviewer** returns `APPROVED`, `REDESIGN` (with a surgical IR node+param fix),
   or `HALT`.
5. On `APPROVED`, a **ForgeCAD handoff bundle** is emitted (`ir.json` editable +
   `model.stl`/`model.step` preview + `manifest.json`).

All run artifacts are saved under `outputs/run_YYYYMMDD_HHMMSS/`. See
`explanation.md` for the full flow, every agent/tool, and file/function ownership.

## Runtime Truth (Important)

| Package | Responsibility | Entry points |
|---|---|---|
| `pipeline.py` | Orchestrator (IR flow) | `python pipeline.py "<prompt>"` or Docker |
| `core/` | provider switch (`providers.py`), model routing, logging, LLM client, process detection | library |
| `geometry_ir/` | IR contract: models + L1 validation + JSON Schema | library |
| `primitives/` | param schemas, builders, registry, compiler, export | library |
| `tools/` | all agent tools (planner_tools, meshlib_tools, meshlib_sandbox) | registered by agents |
| `agents/planner_agent` (`IRPlanner`) | emits Geometry IR; Claude→Gemini fallback | via `pipeline.py` / `adk web` |
| `agents/vision_agent` (`run_vision_verification`) | L3 multimodal verifier (advisory) | via `pipeline.py` |
| `agents/reviewer_agent` (`run_review`) | deterministic-first router + surgical repair | via `pipeline.py` |
| `agents/meshlib_agent` (`run_inspection`) | DEMOTED L4: AI mesh checks for `custom` nodes | via `pipeline.py` |
| `verification/` | L2 `solid_inspector` (ground truth) + L3 `renderer` | library |
| `handoff/` | ForgeCAD bundle (`forgecad_emit`) | via `pipeline.py` on APPROVED |

**Model routing is capability-based** (in `core/providers.py`): Claude leads
code/IR generation (planner, meshlib inspector); Gemini Pro leads vision, reviewer,
and intent extraction; Gemini Flash does cheap classification. Each role falls back
to the other family automatically. **To swap a provider** (or add OpenAI): edit
`core/providers.py` only — no agent/pipeline changes.

Every run writes a self-contained **`report.html`** (open it to see the whole run with images). Run the deterministic edge-case scorecard with `python -m evaluation.run_eval` → `evaluation/report/index.html`.

**Run the whole thing from a browser:** `uvicorn api.app:app --port 8000` then open `http://localhost:8000/` — type a prompt, watch it run live, read the report, edit the IR in 3D with **parameter sliders** and recompile, and accept/iterate. Or drive the API directly: `POST /designs {"prompt": ...}` → `GET /designs/{id}/report` for the summary, `GET /designs/{id}/viewer` for the editable 3D surface (edit params → recompile → re-verify live). Set `HARNESS_API_KEY` to require an `x-api-key` header.

### Known constraints (post-launch hardening)
- **Spec extractor**: uses Gemini 2.5-pro. Occasionally generates 1–2 extra requirements from domain inference (e.g., `overall_diameter_mm` inferred from hub radius). These are now filtered by `extract_spec()` post-processing (drops abstract targets, drops dimensions with `expected=null`). If a run exhausts 6 iterations with uncovered `r1`/`r12`-style requirements, check `01b_spec.json` for phantom requirements and consider rerunning.
- **Frustum orientation**: `r_base` is always at z=0 (the physical bottom). "base diameter 100mm" → `r_base=50`, not `r_top=50`. The planner instruction now enforces this.
- **Taper assert**: always use `"taper": "outward_base"` or `"outward_top"` (string), not `true` (boolean). The L2 inspector normalises `true` → `"outward_base"` as a safety net.
- **Iterate action**: injects prior Q&A history as context. Process detection, spec extraction, and decomposition now use only the original design prompt (not the revision text).

See `explanation.md` for the full file/function map.

## Deep Dive Docs

For full architecture, file-by-file ownership, and how each agent/tool is wired:

- [explanation.md](explanation.md)

Use this when you want to understand:

- which package/file is responsible for what behavior,
- every agent, its tools, and how the tools are registered (ADK `tools=[...]`),
- how to swap model providers granularly via `core/providers.py`,
- how artifacts (`00`–`09` + `forgecad_handoff/`) are produced and consumed.

## Quickstart (Docker Recommended)

### 1) Create `.env`
```bash
cat > .env <<'ENV'
# At least one key is required
ANTHROPIC_API_KEY=your_anthropic_key_here
GEMINI_API_KEY=your_gemini_key_here
ENV
```

### 2) Build image
```bash
docker build -t agentic-cad-pipeline .
```

### 3) Run pipeline with prompt (non-interactive)
```bash
docker run --env-file .env \
  -v "$(pwd)/outputs:/app/outputs" \
  agentic-cad-pipeline \
  python pipeline.py "Create a flange coupling with 8 bolt holes and 3mm fillets"
```

## Full Command Matrix

### Docker build

Standard build:
```bash
docker build -t agentic-cad-pipeline .
```

Fresh rebuild:
```bash
docker build --pull --no-cache -t agentic-cad-pipeline .
```

### Pipeline in Docker

Run with default internal stress-test prompt:
```bash
docker run --env-file .env -v "$(pwd)/outputs:/app/outputs" agentic-cad-pipeline python pipeline.py
```

Run with custom CLI prompt:
```bash
docker run --env-file .env -v "$(pwd)/outputs:/app/outputs" agentic-cad-pipeline python pipeline.py "Design a lightweight impeller with 7 curved blades"
```

Run with interactive planner Q&A (planner can ask follow-up questions):
```bash
docker run -it --env-file .env -v "$(pwd)/outputs:/app/outputs" agentic-cad-pipeline python pipeline.py --interactive "Design a CNC bracket with pocketing"
```

### Pipeline on local terminal

Use only if local CAD/MeshLib dependencies are already installed.

Default internal stress-test prompt:
```bash
python pipeline.py
```

Custom prompt from command line:
```bash
python pipeline.py "Create an SLA-friendly enclosure with 2mm walls"
```

Interactive mode:
```bash
python pipeline.py --interactive "Create an injection-molded housing with draft angles"
```

### MeshLib inspector standalone (terminal)

Use most recent STL found under `outputs/`:
```bash
python agents/meshlib_agent/observe.py
```

Use explicit STL path:
```bash
python agents/meshlib_agent/observe.py outputs/run_20260526_064151/04_outer1_exported_model.stl
```

Use explicit STL + custom primitive plan JSON:
```bash
python agents/meshlib_agent/observe.py \
  outputs/run_20260526_064151/04_outer1_exported_model.stl \
  '{"expected_dims":{"x_mm":100.0,"y_mm":80.0,"z_mm":4.0,"tolerance_mm":0.5},"min_wall_mm":2.0,"manufacturing_process":"FDM_3D_print","primitives":[]}'
```

### ADK Web UI (agent session traces)

```bash
./agents/.agnts/bin/python -m google.adk.cli web \
  --session_service_uri sqlite:///outputs/adk_sessions.db \
  --port 8080 agents
```

Open in browser: `http://127.0.0.1:8080`

### Quick MeshLib import smoke test

```bash
python scratch_test.py
```

## Interactive vs Non-Interactive Behavior

- `--interactive` (or `-i`) enables planner clarification questions.
- Prompt text can be passed directly from CLI arguments.
- If no prompt is provided, `pipeline.py` uses an internal default stress-test prompt.
- In non-TTY mode (common Docker run without `-it`), planner cannot receive manual answers and proceeds with best judgment.

## Project Structure

- `pipeline.py`: orchestrator with inner code-retry and outer redesign loops.
- `src/`: core runtime modules (`llm.py`, `cad_executor.py`, `mesh_inspector.py`, etc.).
- `agents/`: inspector/reviewer runtime modules, planner scaffold, and diagnostics tooling.
- `knowledge_base/manufacturing_profiles.json`: process-aware DFM constraints.
- `outputs/`: logs, generated CAD files, inspection outputs, and reviewer verdicts.

## Output Files Per Run

Each run creates `outputs/run_YYYYMMDD_HHMMSS/` containing:

- `00_pipeline_execution.log`
- `01_design_brief.json` (prompt, detected process, min wall)
- `02_outer*_planner_output.txt` / `02_outer*_planner_revision.txt`
- `03_outer*_ir.json` (the validated Geometry IR for that attempt)
- `04_outer*_model.step|stl`
- `05_outer*_solid_inspection.json` (L2 deterministic intent checks)
- `06_outer*_vision_findings.json` (L3 advisory vision findings)
- `07_outer*_reviewer_verdict.json` (APPROVED/REDESIGN/HALT + node-keyed fix)
- `09_outer*_view_{front,side,top,iso,section}.png` (rendered views)
- on APPROVED: `APPROVED_ir.json` and `forgecad_handoff/` (`ir.json`,
  `model.stl`, `model.step`, `manifest.json`)

## Troubleshooting

### Planner is not asking questions
- Add `--interactive`.
- In Docker, also add `-it` to provide a TTY.

### `agents/planner_agent/agent.py` does not run the real planner flow
- Expected behavior in current codebase.
- Use `pipeline.py` to run the real planner path (`src/llm.py::PlannerAgent`).

### No output files on host
- Ensure mount is exactly `-v "$(pwd)/outputs:/app/outputs"`.

### Model/API failures
- Verify `.env` keys: `ANTHROPIC_API_KEY` and/or `GEMINI_API_KEY`.
- Rebuild image if dependency layers are stale:
  `docker build --pull --no-cache -t agentic-cad-pipeline .`

## Architecture Note

The safety core is deterministic-first validation: reviewer decisions are grounded in static measurements before AI findings, reducing hallucination-driven acceptance.
# capstone_DS_02
