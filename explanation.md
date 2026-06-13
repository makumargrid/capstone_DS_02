# Geometry Agent Harness — Explanation

Living reference for the IR-centric agentic CAD harness: the full flow, every
agent and its tools (and how tools are registered), which file/function owns
which part, and a complete post-launch hardening log. Every source file also
carries a self-documenting header (`WHAT / CALLED BY / CALLS`).

---

## 1. Why this design exists (the problem it solves)

The legacy pipeline regenerated **free-form CadQuery** every loop and verified
only the **tessellated STL**. With no deterministic notion of *design intent* it
leaned on a noisy LLM mesh inspector: merged features passed a
"uniform 2 mm" spec, the AI inspector self-contradicted, and the loop exhausted.

**Root cause:** no deterministic intent ground truth + noisy feedback.

**The fix:** a typed, validated **Geometry IR** (a parametric *feature tree* in
JSON) is the single source of truth. The planner emits IR; a deterministic
compiler builds the solid with per-feature provenance; checks run against the
IR's *declared claims*; the reviewer routes repairs keyed to a specific IR node +
param; ForgeCAD edits the same IR.

---

## 2. End-to-end flow

```
prompt
  → _design_prompt() ............... strip iterate Q&A context / revision suffix
  → detect_process ................. process + DFM profile (uses stripped prompt)
  → extract_spec ................... immutable intent contract (uses stripped prompt)
  → decompose ...................... part vs assembly judgment (uses stripped prompt)

  → Planner Agent ─ emits ─→ Geometry IR (JSON, validated)
                                     │
      ┌──── deterministic compiler (primitives library) ────┐
      │  IR → CadQuery solid (+ per-feature provenance) → STEP/STL │
      └──────────────────────────────────────────────────────────┘
                                     │
   L1 validate_plan ......... schema + refs            [geometry_ir/validate.py]
   compile_design ........... geometry authority       [primitives/compiler.py]
   L2 inspect_solid ......... deterministic intent GT   [verification/solid_inspector.py]
   L3 render + Vision ....... advisory "thinking w/ images" [verification/renderer.py + agents/vision_agent]
   L4 MeshLib (DEMOTED) ..... only for custom/mesh_only [agents/meshlib_agent + tools/meshlib_*]
   Reviewer ................. APPROVED / REDESIGN(node-keyed) / HALT [agents/reviewer_agent]
   Coverage gate ............ every REQUIRED spec req must be met [core/spec.check_coverage]
   Doom-loop valve .......... same req fails 2× → downgrade to preferred [pipeline.py]
                                     │
   ForgeCAD handoff: ir.json + ir_original.json + model.stl + model_original.stl
                     + model.step + manifest.json [handoff/]
   Acceptance gate .......... human accept/reject + durable registry record [core/registry.py]
```

The planner receives the **full** prompt (including Q&A context and revision text).
`_design_prompt()` strips those blocks so process/spec/decompose see only the
core design intent — preventing iterate's revision text from corrupting detection.

---

## 3. Directory map (modular by responsibility)

| Package | Responsibility |
|---|---|
| `core/` | shared infra: env bootstrap, provider switch, model routing, logging, direct LLM client, process detection |
| `geometry_ir/` | the IR **contract**: feature-tree grammar (models) + L1 validation + JSON Schema |
| `primitives/` | the reusable **library**: param schemas, builders (geometry store), registry tables, compiler, export |
| `tools/` | **all agent tools**, grouped + commented by the agent that registers them |
| `agents/` | the ADK agents: planner, vision, reviewer, meshlib |
| `verification/` | L2 deterministic inspector + L3 renderer |
| `handoff/` | ForgeCAD bundle emitter (IR + STL/STEP + originals) |
| `pipeline.py` | the orchestrator |
| `api/` | HTTP product API over the pipeline (Phase 4+) |
| `webui/` | the browser front-end: dashboard + run page (static, served at `/ui`) |
| `reporting/` + `evaluation/` | per-run report + deterministic eval scorecard (Phase 3) |
| `knowledge_base/` | manufacturing DFM profiles (JSON) |
| `config/` | YAML-driven configuration: `primitives/`, `process/manufacturing_profiles.json`, `inspection_thresholds.yaml` |
| `skills/` | Agent skill files: `planner/SKILL.md`, `vision/SKILL.md`, `reviewer/SKILL.md` |
| `knowledge/` | Knowledge corpus for agents |

---

## 4. core/ — shared infrastructure (granular provider modularity)

| File | Key symbols | Responsibility |
|---|---|---|
| `core/env.py` | `bootstrap_env` | process-wide env bootstrap: loads `.env`, defaults `GOOGLE_GENAI_USE_VERTEXAI=false`, mirrors `GEMINI_API_KEY ↔ GOOGLE_API_KEY` so both ADK and direct google-genai calls find the key. |
| `core/providers.py` | `PROVIDERS`, `AGENT_MODELS`, `FALLBACK_ORDER`, `provider_of`, `available`, `fallback_model` | **THE single provider switch-point.** |
| `core/model_config.py` | `get_model_name`, `get_fallback_model_name`, `safe_parse_json`, `_patch_adk_registry` | model resolution + ADK registry patch (driven by providers) |
| `core/llm_client.py` | `call_llm` | direct (non-ADK) LLM call w/ failover; used by process_detector, spec, decompose |
| `core/adk_runner.py` | `run_agent` | stateless ADK agent run with Claude→Gemini failover; used by vision + meshlib |
| `core/logger.py` | `get_agent_logger` | per-run logging (creates file handler for `00_pipeline_execution.log`) |
| `core/process_detector.py` | `detect_process`, `load_profile` | manufacturing process + DFM profile selection |
| `core/spec.py` | `extract_spec`, `check_coverage`, `coverage_feedback`, `decompose`, `_design_prompt` | intent contract + coverage gate + iterate context stripping |
| `core/registry.py` | `request_acceptance`, `record` | human acceptance gate + durable `10_acceptance_record.json` / `registry.jsonl` |

**Granular provider swap.** Everything provider-specific lives in `core/providers.py`:
- **Swap a role's model** (e.g. planner → Gemini): change one string in `AGENT_MODELS`.
- **Add a new provider** (e.g. OpenAI): add one entry to `PROVIDERS`.
- **Re-order failover:** edit `FALLBACK_ORDER`.
No agent or pipeline code changes for any of these.

**Model routing:**
- **Claude** → planner + meshlib inspector (precise structured IR, strict schema, tool use).
- **Gemini Pro** → vision verifier, reviewer, intent extraction, decompose (analytical + multimodal).
- **Gemini Flash** → cheap process/dimension classification.

---

## 5. geometry_ir/ — the IR contract

| File | Key symbols | Responsibility |
|---|---|---|
| `geometry_ir/models.py` | `Design`, `Feature`, `Envelope`, `IR_VERSION` | the feature-tree grammar (Pydantic v2) |
| `geometry_ir/validate.py` | `validate_plan`, `_validate_pattern`, `export_json_schema`, `KNOWN_TYPES` | L1 node-keyed validation + the versioned JSON Schema |

`validate_plan(ir) → {valid, errors:[{node, detail}]}` in three layers: design
structure → per-feature params (via `primitives.PARAM_MODELS`) → reference
integrity. Patterns validate count + nested feature; `custom` skips param schema.

---

## 6. primitives/ — the reusable library

| File | Key symbols | Responsibility |
|---|---|---|
| `primitives/params.py` | `PARAM_MODELS` + `CylinderParams`/`ConeParams`/`FrustumParams`/`BoxParams`/`HoleParams`/`SphereParams`/`TubeParams`/`ProfileParams` | typed param schema per primitive |
| `primitives/builders.py` | `build_cylinder/cone/frustum/box/hole/sphere/tube/profile` | the **geometry store** — how each primitive's solid is built |
| `primitives/registry.py` | `LEAF_BUILDERS`, `FORGECAD_MAP`, `list_primitives` | lookup tables binding the vocabulary |
| `primitives/compiler.py` | `compile_design`, `FeatureProvenance`, `_build_pattern`, `_run_custom` | IR → `cq.Solid` + provenance (geometry authority) |
| `primitives/anchoring.py` | `resolve_anchor`, `_face_point` | relational placement (to, from_face, to_face, align, offset) |
| `primitives/export.py` | `export_solid` | `cq.Solid` → STEP / STL |

**Canonical primitive set:** `{cylinder, cone, frustum, box, hole, sphere, tube, profile}`.
The registry guard in `primitives/registry.py` asserts this set matches the loaded YAMLs
at import time. Removing a YAML crashes with ImportError (loud, not silent).

**ADD A PRIMITIVE:** add YAML in `config/primitives/` + `<Name>Params` (params.py) +
`PARAM_MODELS` entry → `build_<name>` (builders.py) → update `_CANONICAL_PRIMITIVES`
in registry.py → a builder unit test.

---

## 7. Agents & tools (ADK)

Each agent is declared `root_agent = Agent(name, model, description, instruction,
tools=[...])` and driven by a `Runner` + session service. The model is chosen by
`core.model_config.get_model_name(<role>)`. **Tools are registered by passing plain
functions in `tools=[...]`** — ADK derives each tool's schema from the function's
signature + docstring.

| Agent | File | Model role | Tools (from `tools/`) |
|---|---|---|---|
| Planner | `agents/planner_agent/agent.py` (`IRPlanner`, `root_agent`) | `planner` | `planner_tools`: list_primitives, get_primitive_schema, validate_plan, ask_user |
| Vision Verifier | `agents/vision_agent/agent.py` (`run_vision_verification`) | `inspector` | none (images passed as inline `types.Part`) |
| Reviewer | `agents/reviewer_agent/agent.py` (`run_review`) | `reviewer` | none (deterministic-first; LLM only narrates) |
| MeshLib Inspector | `agents/meshlib_agent/agent.py` (`run_inspection`) | `inspector` | `meshlib_tools`: execute_meshlib_code, explore_meshlib_api |

**`tools/planner_tools.py`** — registered by the Planner:
- `validate_plan(ir_json)`: validates IR; when `valid=True` caches the IR in thread-local
  `_tl.last_valid_ir` and returns an `ACTION_REQUIRED` key forcing the model to re-emit
  the JSON block. `get_last_valid_ir()` is exported for use by `extract_ir` as a fallback.
- `list_primitives()`, `get_primitive_schema(name)`: discovery tools.
- `ask_user(question)`: blocked by `_make_ask_user_tool` — uses terminal stdin in CLI mode
  or the API's blocking question handler in browser mode.

**`tools/meshlib_tools.py`** — registered by MeshLib Inspector (L4):
- `execute_meshlib_code(script, mesh_path)`: runs in subprocess sandbox.
- `explore_meshlib_api(path)`: introspects `mrmeshpy` for unknown method names.

**`IRPlanner`** (`agents/planner_agent/agent.py`):
- Persistent-session wrapper used by the pipeline for all outer iterations within a run.
- `__init__(interactive, process, question_handler, session_db_uri=None, reuse_session_id=None)`:
  - `session_db_uri`: if set, uses ADK `DatabaseSessionService` (SQLite) so sessions
    survive across runs. pipeline.py passes `sqlite+aiosqlite:///outputs/adk_sessions.db`.
  - `reuse_session_id`: if set, the planner joins an **existing** session — the iterate
    child run inherits full conversation history from the parent run.
  - `self._log = logger` by default; `pipeline.py` replaces it with `log` so planner
    messages appear in `00_pipeline_execution.log`.
- `_build(model)`: rebuilds agent + runner for `model` (ADK resolves provider at build time).
- `_run(message)`: invokes; falls back to `self.fallback_model` on exception or empty response.
- `extract_ir(text)`: primary = `safe_parse_json(text)`; fallback = `get_last_valid_ir()`
  cache (catches the "Validation passed." no-JSON pattern).

**`PLANNER_INSTRUCTION`** key additions (see `agents/planner_agent/agent.py`):
- **Question style guide**: batch all unknowns into ONE ask; lead with use-case not parameter;
  use ASCII diagrams for spatial choices; always state industry standard first.
- **Frustum orientation rule**: `r_base` = radius at z=0 (physical bottom), `r_top` = at
  z=height (physical top). "base diameter 100mm" → `r_base=50`. Always larger at base.
  Always assert `"taper": "outward_base"` (string, not boolean `true`).
- **Pattern geometry**: formula for feature placement relative to parent params.

**Reviewer is deterministic-first:** verdict computed in `_decide` from L2 node-keyed
checks (vision can never flip an L2-passing part). All failing checks returned (not just
the most-blocking), so multi-failure runs converge faster.

---

## 8. verification/ — the quality layers

| File | Key symbols | Layer |
|---|---|---|
| `verification/solid_inspector.py` | `inspect_solid`, `inspect_ir`, `_check_uniform_thickness`, `_check_taper`, `_check_bore` | L2 deterministic intent ground truth (node-keyed) |
| `verification/renderer.py` | `render_views`, `_VIEWS` | L3 headless multi-view PNGs |

**L2 checks (node-keyed, severity-tagged):**
- **Blocking (structural):** single_solid, envelope, feature_contributes, hole_edge_clearance,
  self_intersecting, watertight, parent_contact, count, uniform_thickness, taper, bore,
  fillet_radius_mm, chamfer_length_mm.
- **DFM (advisory):** overhang_angle, bridge_span, min_hole_diameter_mm, min_feature_size_mm,
  draft_angle.

**Verdict contract:** `geometrically_valid` (blocking only), `manufacturable` (DFM only),
`valid` (backwards-compat == geometrically_valid). Certificate reports both flags;
never claims certified when manufacturable=False.

---

## 9. handoff/ — ForgeCAD bundle

`handoff/forgecad_emit.py`: `emit_forgecad_bundle(ir, out_dir)` writes:
- `ir.json` — editable source of truth (overwritten on recompile)
- `ir_original.json` — immutable original (written once, never overwritten)
- `model.stl` / `model.step` — preview geometry (overwritten on recompile)
- `model_original.stl` — immutable original STL (written once, never overwritten)
- `manifest.json` — per-node `forgecad_builder`, `native_editable`, provenance

The `_original` files enable the viewer's "Reset to original" button. They are
only written if they don't already exist (subsequent recompiles leave them intact).

`load_and_recompile(dir)` is the round-trip: edit params → recompile → identical solid.
`MANIFEST_SCHEMA` validates the manifest. The IR JSON is the single artifact crossing
the JS/Python boundary.

---

## 10. pipeline.py — orchestrator

`run_pipeline(prompt, output_base_dir, interactive, run_id, question_handler,
parent_session_id)`:

**Setup phase:**
1. `_design_prompt(prompt)` → strips `<<<QA_START>>>...<<<QA_END>>>` blocks and
   `REVISION REQUESTED:` suffix. The stripped prompt `dp` is used for process/spec/decompose;
   the full prompt (with context) is passed to the planner.
2. `detect_process(dp)` → manufacturing process + DFM profile.
3. `extract_spec(dp)` → immutable intent contract (saved `01b_spec.json`).
4. `IRPlanner(session_db_uri=..., reuse_session_id=parent_session_id)` → creates (or joins)
   the ADK session. Session_id saved to `planner_session_id.txt` for iterate reuse.
5. `planner._log = log` → planner messages appear in `00_pipeline_execution.log`.
6. `decompose(dp)` → part vs assembly judgment.

**Per outer iteration (`MAX_OUTER=6`):**
- L1 validate → compile → export → L2 inspect → L3 render+vision → (L4 meshlib) → reviewer
- On APPROVED: `check_coverage(spec, l2, ir)` → coverage gate
- **Doom-loop safety valve** (`_coverage_miss_streak`): if the same requirement fails
  2 consecutive times, it's downgraded to "preferred" (logged as `[COVERAGE] Req Xn
  downgraded`) and the run continues instead of exhausting all 6 attempts.
- Streak counter resets for requirements that become covered in later iterations.
- On coverage pass → `emit_forgecad_bundle` → acceptance gate → `registry.record` → `_report`.

**`_design_prompt(prompt)` helper:**
```
<<<QA_START>>> ... <<<QA_END>>>        ← stripped (new format)
PRIOR Q&A CONTEXT ... \n\n            ← stripped (legacy format)
<actual design request>                ← returned
REVISION REQUESTED: ...                ← stripped
```
The delimiter `<<<QA_START/END>>>` is used because planner questions can contain
`\n\n` (multi-paragraph), which would fragment `\n\n`-based splitting.

**`_run_assembly`** — same loop as the part path, but operates on Assembly IR
(components + mates → compile_assembly → inspect_assembly). Requires its own
`from agents.reviewer_agent import run_review` import (the import in `run_pipeline`
is local and invisible to module-level `_run_assembly`).

Artifacts per run: `00` log, `01` design_brief, `01b` spec, `01c` decomposition,
`02` planner text, `03` ir.json, `04` step/stl, `05` L2, `06` vision, `07` verdict,
`08` coverage, `09` view PNGs, `planner_session_id.txt`, `APPROVED_ir.json`,
`forgecad_handoff/`.

---

## 11. Status

- **Verification:** Docker is the authoritative runtime for the full suite because
  it installs CadQuery, MeshLib, ADK, FastAPI, rendering dependencies, and `pytest`.
  Fresh Docker verification on 2026-06-08: `127 passed, 7 warnings in 50.92s`.
  Local lightweight checks can run without CAD dependencies, but local full
  collection may fail with `No module named cadquery` unless CadQuery/MeshLib are installed.
- Phase 1 (intent) + Phase 2 (assembly) + Phase 3 (observability/eval) + Phase 4 (API) +
  Phase 5 (ForgeCAD viewer + sliders + reset) + post-launch hardening complete.
  Next: Phase 6 (trace flywheel), Phase 7 (Temporal durability), Phase 8 (hardening/auth).

---

## 12. Robustness fixes (post-restructure)

Four issues surfaced by a Docker run were fixed:

1. **Envelope doom loop (convergence).** `verification/solid_inspector.py` now
   treats the overall envelope as a **coarse** bound: `eff_tol = max(declared_tol,
   7% of dim)` (`ENV_REL_TOL`). Gross/collapsed parts still fail.
2. **Feature thickness false-positive.** `_check_uniform_thickness` reads the
   declared thickness PARAM (box→min dim, tube→wall) — exact.
3. **Provider failover for all agents.** `core/adk_runner.run_agent` gives vision +
   meshlib the same Claude→Gemini failover the planner had.
4. **Event-loop noise.** `core/_quiet.py` suppresses the benign "Event loop is closed"
   httpx-cleanup message via both `unraisablehook` and `asyncio` logger filter.

---

## 13. Phase 1 — independent intent contract

**Problem:** Planner wrote its own asserts → could converge by declaring a trivial bar
(7 flat plates satisfying only `count=7`). Phase 1 makes intent independent:

| File | Responsibility |
|---|---|
| `core/spec.py :: extract_spec(dp)` | Immutable requirement list. LLM (Gemini, `intent` role) + deterministic domain augmentation + offline regex fallback. **Post-processing filter** drops: `feature_present` with multi-word/underscore targets (phantom abstract concepts); `dimension` with `expected=null` (uninformative). |
| `core/spec.py :: check_coverage` | Deterministic gate: every REQUIRED req must be met by a passing L2 check OR IR structure. `_dim_from_params` maps spec params to IR primitive fields (e.g., `base_diameter_mm` → `r_base * 2`). |
| `core/spec.py :: coverage_feedback` | Spec-targeted REDESIGN guidance. Detects `r_base`/`r_top` swap (measured base ≈ expected top) and emits surgical correction with exact values. |
| `core/registry.py` | `request_acceptance` + `record`: human gate + `10_acceptance_record.json` + `registry.jsonl`. |

**`_EXTRACT_INSTRUCTION`** hard constraints:
- `feature_present` targets must be single concrete words (`hub`, `bore`, `holes`, etc.),
  not abstract concepts (`smooth_surfaces`).
- `dimension` claims only assert numbers **explicitly stated** in the prompt (no inference).

Tests: `tests/test_spec.py` (6).

---

## 14. Phase 2 — decomposition + assembly

Same loop as Phase 1 with a decomposition judgment up front.

| File | Responsibility |
|---|---|
| `core/spec.py :: decompose(dp)` | Part vs assembly (uses stripped design prompt `dp`). |
| `geometry_ir/assembly.py` | Assembly IR + `validate_assembly` (grounded kinematic tree). |
| `primitives/assembly.py` | `compile_assembly`: mate solver — LLM declares mates, code solves transforms. |
| `verification/interface_inspector.py` | L-ASM: interference / contact / concentric / fit checks. |
| `verification/assembly_inspector.py` | `inspect_assembly`: per-component L2 + interfaces. |
| `agents/planner_agent` | `generate_assembly` / `revise_assembly` emit/repair Assembly IR. |
| `pipeline.py :: _run_assembly` | Assembly branch with local `run_review` import. |

---

## 15. Phase 3 — observability + deterministic eval

| File | Responsibility |
|---|---|
| `reporting/report.py :: build_report(run_dir)` | Self-contained `report.html`: prompt, spec, decomposition, check table, coverage, verdict, acceptance, embedded view PNGs. |
| `evaluation/cases.py` | Edge-case library (11 cases: interference, cycles, wrong-count, etc.). |
| `evaluation/run_eval.py` | Runs deterministic spine only (no LLM) → `evaluation/report/index.html`. |

---

## 16. Phase 4 — Product API

`api/app.py` exposes the pipeline over HTTP.

| Endpoint | Purpose |
|---|---|
| `POST /designs` | start a run → `{run_id, status_url}` (body: `{prompt, interactive?}`) |
| `GET /designs` | list runs + states |
| `GET /designs/{id}/status` | state, verdict, artifacts, report_url, pending_question, **qa_history** |
| `GET /designs/{id}/report` | `report.html` |
| `GET /designs/{id}/log` | tail of pipeline execution log + state (drives live log UI) |
| `GET /designs/{id}/artifacts/{name:path}` | run artifact (path-traversal-safe) |
| `POST /designs/{id}/iterate` | child run with Q&A context + revision feedback + session reuse |
| `POST /designs/{id}/answer` | resume blocked planner thread (browser question bridge) |
| `POST /designs/{id}/approve` | write acceptance record + **regenerate report.html** |
| `WS /ws/designs/{id}/stream` | live status frames until terminal state |
| `GET /designs/{id}/viewer` | ForgeCAD viewer page (Phase 5) |
| `POST /recompile` | edit→recompile→re-verify an IR; returns checks + new STL |

**Key implementation details:**

- **`qa_history`**: `RUNS[rid]` dict includes `qa_history: []`. Each answered question appends
  `{"q": question, "a": answer}`. Exposed in `/status`.

- **`POST /iterate`** context format:
  ```
  <<<QA_START>>> (do NOT re-ask)
  Q: <question text (may be multiline)>
  A: <answer text>
  ---
  <<<QA_END>>>
  <original_prompt>

  REVISION REQUESTED: <feedback>
  ```
  Uses `<<<QA_START/END>>>` delimiters (not `\n\n` parsing) because planner questions
  contain blank lines that would fragment `\n\n`-based splits.

- **Iterate session reuse**: reads `{parent_run_dir}/planner_session_id.txt`; passes to
  `run_pipeline(parent_session_id=...)` → `IRPlanner(reuse_session_id=...)`. The child
  planner joins the parent's existing ADK session and sees the full prior conversation.

- **`POST /approve`**: writes `10_acceptance_record.json` then calls `build_report(run_dir)`
  so the report immediately shows the accepted/rejected state.

- **RUNNER**: module-level so tests inject a fast, LLM-free fake. Fake must accept
  `**kwargs` to absorb `parent_session_id` and other future params.

---

## 17. Phase 5 — ForgeCAD editable surface

The handoff bundle is now *operable* in a browser with full parameter editing.

| File | Responsibility |
|---|---|
| `api/recompile.py :: recompile_ir(ir)` | stateless: validate → compile → inspect an EDITED IR; returns `{valid, stage, checks, stl_b64}`. |
| `api/viewer.py :: viewer_html(run_id)` | self-contained page: loads handoff bundle, renders in 3D, parameter sliders, reset button. |

**`viewer_html` features (current):**

1. **Inlined binary STL parser** — 30-line JS function `parseBinSTL(buf)` creates
   `THREE.BufferGeometry` directly from the binary STL `ArrayBuffer`. No CDN dependency
   for the geometry loader (CDN failures were silently blanking the view).

2. **Error handling in `show(buf)`** — wrapped in try-catch; errors display in `#msg`
   instead of silently disappearing to the JS console.

3. **Dynamic camera distance** — computed from the parsed geometry's bounding-box diagonal
   (`_camDist = diag * 1.8`). The part always fills the viewport regardless of size in mm.

4. **Mouse-drag orbit + scroll zoom** — `mousedown/mousemove/mouseup` for orbit; `wheel`
   for zoom. No auto-rotate (users can inspect freely).

5. **Parameter sliders panel** — `buildParamPanel(ir)` walks every feature's numeric params
   (including nested pattern feature params) and creates a labelled range slider + number
   input per param. Slider range defaults to `[value × 0.1, value × 4.0]`.
   On change: updates the IR object → stringifies to textarea → schedules 600ms debounce
   recompile. Panel rebuilds after each recompile to stay in sync.

6. **"Reset to original" button** — fetches `model_original.stl` + `ir_original.json`
   from the handoff dir, restores the 3D view, resets the textarea, and rebuilds sliders.
   The originals are written once by `emit_forgecad_bundle` and never overwritten.

**Flow:** `GET /designs/{id}/viewer` → browser fetches handoff IR + STL → user edits
params via sliders or textarea → `POST /recompile {ir}` → server runs deterministic spine
→ returns new STL (base64) + node-keyed checks → page re-renders.

---

## 18. Web UI (`webui/`) — the single front door

A no-build, static front-end mounted by FastAPI at `/ui` (`GET /` redirects there).

| File | Responsibility |
|---|---|
| `webui/index.html` + `static/app.js` | dashboard: prompt → `POST /designs` → run list |
| `webui/run.html` + `static/run.js` | run page: WS status stream + tabs (Summary / 3D & Edit / Actions) |
| `webui/static/style.css` | shared styling |

**User flow:** open `/` → type prompt → watch live status → Summary tab shows report →
3D & Edit shows viewer with sliders → Accept/Reject or Iterate from Actions tab.

---

## 19. Live logs, error surfacing, and the 'Event loop is closed' fix

**Event-loop teardown race (resolved).** `core/_quiet.py` neutralises both the
`unraisablehook` path and the `asyncio` logger path for the exact "Event loop is closed"
message, so real errors still show.

**Live logs in UI.** `GET /designs/{id}/log` returns log tail + state. Summary tab shows
live log, error panel, and report iframe. Every pipeline exit builds a report.

**Convergence (multi-failure runs).** Reviewer returns ALL failing node-keyed fixes
(most-blocking first).

---

## 20. Post-launch run hardening

Issues found and fixed during real end-to-end runs after the initial launch:

| Fix | Root cause | Files changed |
|---|---|---|
| **"no IR emitted"** — planner says "Validation passed." without JSON block | `validate_plan` tool returned success; model treated it as submission | `tools/planner_tools.py` (cache + ACTION_REQUIRED), `agents/planner_agent/agent.py` (fallback extraction) |
| **`run_review` NameError in assembly path** | `from agents.reviewer_agent import run_review` is local to `run_pipeline`; `_run_assembly` is module-level and can't see it | `pipeline.py` — added import inside `_run_assembly` |
| **Iterate prompt corrupts process/spec/decompose** | Q&A context + revision text bled into process detection and spec extraction, injecting wrong keywords | `api/app.py`, `pipeline.py` — `<<<QA_START/END>>>` delimiters + `_design_prompt()` |
| **Phantom spec requirements doom every run** | Gemini spec extractor invents abstract targets (`smooth_aerodynamic_surfaces`) and inferred dimensions (tip_diameter = 2 × hub_radius) | `core/spec.py` — `_EXTRACT_INSTRUCTION` constraints + post-processing filter |
| **r_base / r_top consistently inverted** | Planner confused frustum orientation; coverage feedback too vague | `agents/planner_agent/agent.py` (FRUSTUM ORIENTATION rule), `core/spec.py` (swap-detection hint in `coverage_feedback`) |
| **`"taper": true` uses wrong L2 direction** | `_check_taper(direction=True)` falls to `else` branch (outward_top) | `verification/solid_inspector.py` — normalise non-string → `"outward_base"` |
| **MeshLib error context** | Error context injection improved | `tools/meshlib_tools.py` |
| **3D viewer blank** | CDN STLLoader failed silently; no error handling in `show()` | `api/viewer.py` — inlined STL parser + try-catch + error surfacing |
| **Coverage doom-loop** | Same phantom req failed 6× with no escape; run always died at "Out of attempts" | `pipeline.py` — `_coverage_miss_streak` doom-loop safety valve (downgrade after 2× miss) |
| **Baseline model lost on slider edits** | No original copy of model/IR saved at first approval | `handoff/forgecad_emit.py` (write `_original` files once), `api/viewer.py` (Reset to original button) |
| **Report stale after browser approval** | `/approve` wrote acceptance record but did not regenerate `report.html` | `api/app.py` — call `build_report` after writing record |
| **ADK session lost on iterate** | Each run creates fresh `InMemorySessionService`; full conversation history discarded | `agents/planner_agent/agent.py` (`session_db_uri`, `reuse_session_id`), `pipeline.py` (save session_id), `api/app.py` (pass to child run) |
| **Planner logs invisible in pipeline file** | Module-level `logger` ≠ pipeline's file logger | `agents/planner_agent/agent.py` (`self._log`), `pipeline.py` (`planner._log = log`) |
| **Assembly path wrong `run_review` scope** | Already documented above | `pipeline.py` |

**Current coverage gate hardening:**

`core/spec.py::extract_spec` post-processing filter:
- Drops `feature_present` where `_is_verifiable_target(target)` is False (multi-word,
  underscore-compound, or empty) — prevents abstract phantom requirements.
- Drops `dimension` where `expected` is `None` — prevents uninformative "must exist" rules.

`pipeline.py` doom-loop valve:
- `_coverage_miss_streak: dict` tracks consecutive failures per requirement ID.
- After **2 consecutive misses**: requirement downgraded to `"preferred"`, log emits
  `[COVERAGE] Req Xn stuck — downgrading to preferred`.
- Streak resets when requirement is next covered.
- General safety net for any prompt.
