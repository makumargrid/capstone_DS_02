# fix.md — The build journey of the Geometry Agent Harness

This is the story of the platform: where it started, every problem we hit, what I
thought the real cause was, how we fixed it, and how the whole thing works now.
Read top-to-bottom and you'll understand both the *why* and the *who-does-what*.

> Companion docs: `explanation.md` (file/function reference), `README.md` (how to run).

---

## 0. Where it started

The original system was an **adversarial multi-agent pipeline over free-form
CadQuery**: a planner LLM wrote raw CadQuery code each iteration; we executed it,
exported an STL, ran a deterministic mesh check + an LLM "MeshLib inspector," and
a reviewer voted APPROVED / REDESIGN / HALT.

It worked on simple shapes but **could not converge** on the stress-test impeller.
Worse, it sometimes *passed wrong parts*.

---

## 1. Root diagnosis — why the legacy design was doomed

**Problem.** The pipeline regenerated free-form code and verified only the
tessellated **mesh**. It had no deterministic notion of *design intent*.

**My opinion.** This is the fatal flaw: you cannot reliably verify intent from a
mesh. An 8.63 mm merged-blade mass *passed* a "uniform 2 mm" spec (the wall check
was one-sided), and the only intent signal was a noisy LLM inspector that
contradicted itself (0.05 mm vs 8.63 mm). The reviewer correctly distrusted it and
the loop exhausted. Every later band-aid (Z-floor filters, looser tolerances, more
loops) treated symptoms. The real cause: **no deterministic intent ground truth +
noisy feedback.**

**The fix (architectural pivot).** Replace free-form code with a typed, validated
**Geometry IR** — a parametric *feature tree* in JSON — as the single source of
truth. The planner emits IR; a deterministic compiler builds it; checks run
against the IR's *declared claims*; repairs are keyed to a specific IR node+param;
ForgeCAD edits the same IR.

---

## 2. The IR-centric harness (the rebuild)

**How it works — the layers and who owns them:**

| Stage | Owner | Responsibility |
|---|---|---|
| Intent contract | `core/spec.py` | extract an immutable Spec from the prompt (see §7) |
| Planning | `agents/planner_agent` (`IRPlanner`) + `tools/planner_tools.py` | emit a validated Geometry IR; tools: list_primitives, get_primitive_schema, validate_plan, ask_user |
| Contract | `geometry_ir/` | the IR grammar (`models.py`) + L1 validation (`validate.py`) |
| Library | `primitives/` | param schemas, builders (geometry store), registry, compiler, export |
| L2 ground truth | `verification/solid_inspector.py` | deterministic checks vs declared claims |
| L3 vision | `verification/renderer.py` + `agents/vision_agent` | multi-view render + advisory multimodal check |
| L4 (demoted) | `agents/meshlib_agent` + `tools/meshlib_*` | AI mesh checks, only for `custom`/mesh-only nodes |
| Routing | `agents/reviewer_agent` | deterministic-first APPROVED / REDESIGN / HALT |
| Handoff | `handoff/forgecad_emit.py` | editable ir.json + STL/STEP + manifest |
| Orchestration | `pipeline.py` | runs the whole loop |
| Infra | `core/` | providers, model routing, logging, LLM client, process detection |

**Why it converges where the old one drifted:** L2 measures the *compiled solid +
per-feature provenance* against the IR's declared asserts (count the 7 blade
instances directly; two-sided thickness; bore presence; rotation-invariant
diameter). Failures are node-keyed, so the reviewer issues *surgical, single-node*
repairs the planner can apply exactly — instead of prose that caused drift.

---

## 3. Modularity restructure

**Problem.** Everything lived under `src/` with dead code from the legacy
pipeline; provider logic was scattered; the layout didn't reflect the mental model.

**My opinion.** A harness people will extend must be modular at a granular level —
especially swapping model providers — and self-documenting.

**Fix.** Reorganised into purpose-named packages (`core/`, `geometry_ir/`,
`primitives/`, `tools/`, `agents/`, `verification/`, `handoff/`), deleted all dead
code, and gave every file a `WHAT / CALLED BY / CALLS` header. **Granular provider
modularity** lives in one file, `core/providers.py`: swap a role's model by editing
`AGENT_MODELS`; add a provider by adding one `PROVIDERS` entry (the ADK registry
patch wires it via `importlib`). No agent/pipeline code changes.

---

## 4. Robustness fixes (surfaced by real runs)

| Problem | Opinion | Fix | Owner |
|---|---|---|---|
| Envelope doom loop: a correct part whose blades protrude ~1 mm above the hub failed a sub-mm `envelope_z` gate forever | The overall envelope is a *coarse* bound; precision belongs to per-feature asserts. Forcing the bbox to equal a feature dim is wrong dimensioning | Envelope tol = `max(declared, 5% of dim)` (`ENV_REL_TOL`); gross errors still fail | `verification/solid_inspector.py` |
| Twisted-blade false thickness: a `blade` of `width=2` read 21.7 mm via AABB | AABB is only valid for axis-aligned prisms; twist makes it meaningless | Read the declared thickness PARAM (blade→width, box→min-dim) — exact + twist-proof; AABB only as fallback | `verification/solid_inspector.py` |
| Only the planner had provider failover → vision/meshlib crashed with ADK tracebacks when a provider was down | Failover must be shared infra, not planner-only | `core/adk_runner.run_agent` — stateless run with Claude→Gemini failover, used by vision/meshlib | `core/adk_runner.py` |
| "Event loop is closed" httpx noise | Cosmetic; suppress only that exact unraisable | `core/_quiet.py` re-installs the `sys.unraisablehook` | `core/_quiet.py` |

Reviewer envelope feedback is now **bidirectional**: a built-vs-declared mismatch
can be fixed by growing the geometry OR correcting an over-declared envelope.

---

## 5. The deepest problem — the planner graded its own exam (intent circularity)

**Problem.** A "centrifugal impeller … 7 radial blades" run got **APPROVED in one
iteration** as **7 flat plates**. Why? The planner produced *both* the geometry
*and* the `asserts` that verify it, and declared only `count: 7`. Every check was
honest, but they only verified *what the planner chose to claim* — not what the
user asked for. Same prompt → different results, because the acceptance bar was
re-invented (and minimised) every run.

**My opinion.** This is the single most important flaw: the system guaranteed
*internal consistency* (geometry matches the planner's own asserts) but **not
intent fidelity** (geometry matches the user's intent). "APPROVED" meant "the
planner satisfied the planner" — which is worthless if it isn't what was asked.
And after APPROVED, nothing was recorded as accepted-against-intent.

**Fix — Phase 1: an independent, immutable intent contract.** (See §7.)

---

## 6. Decomposition — building objects in parts (Phase 2)

**Question raised:** can the agent build an object as separately-verified parts,
then merge them, and does that help accuracy?

**My opinion (researched).** Yes for *true assemblies* (AC unit, gearbox,
enclosure+lid), no for *monolithic parts* (an impeller is one solid). The IR
already decomposes at the *feature* level; Phase 2 adds *component* level. The
real bottleneck is exactly what was worried about: **the merge.** Independent part
accuracy does NOT guarantee assembly accuracy (tolerance stack-up, datum mismatch,
interference, mating-feature misalignment). Decomposition only *raises* accuracy if
the interfaces are **explicit, declared, and deterministically verified** —
otherwise it just hides failure.

**The principle that makes it work:** **never let the LLM compute the assembly
math.** The planner declares mate *intent*; deterministic code *solves* the
placement; interface checks + vision verify the combination. (See §8.)

---

## 7. Phase 1 (DONE) — intent independence

**How it works:**
- `core/spec.py :: extract_spec(prompt)` — runs **before and independent of** the
  planner (its own `intent` model role) → an immutable list of requirements
  (`feature_present / count / swept / taper / bore_diameter_mm /
  uniform_thickness_mm / dimension`). Adds deterministic domain knowledge
  (impeller/turbine/fan ⇒ blades must be *swept*, not flat) and has an offline
  regex fallback.
- The planner receives the Spec as a **contract it must cover** (it cannot weaken
  it).
- `core/spec.py :: check_coverage(spec, l2_checks, ir)` — deterministic gate: every
  REQUIRED requirement must be met by a passing L2 check OR by IR structure
  (feature present / swept-blade / named-dimension param). Uncovered → REDESIGN
  with spec-targeted feedback (`coverage_feedback`).
- `core/registry.py` — after geometry is valid (L2) **and** intent is covered, a
  human **acceptance gate** runs (interactive) and a record is persisted
  (`10_acceptance_record.json` + append-only `outputs/registry.jsonl`).
  **APPROVED(harness) ≠ ACCEPTED(user).**

**Result:** the flat-blade impeller is now *rejected* — the `swept` requirement is
uncovered, so the planner is forced to use a real swept `blade`. Responsibility:
intent lives in `core/spec.py`; acceptance/persistence in `core/registry.py`;
the gate is wired in `pipeline.py`.

---

## 8. Phase 2a (DONE) — assembly foundation

**How it works:**
- `geometry_ir/assembly.py` — the **Assembly IR**: `components` (each a full
  `Design`) + `mates` (declared interface contracts). One component is `grounded`;
  `validate_assembly` enforces a **grounded kinematic tree** (one ground, no
  cycles, no floating parts).
- `primitives/assembly.py` — the **mate solver + multi-body compiler**: the planner
  declares mates (`stack_on`, `concentric`, `coincident_face`, `custom`);
  `compile_assembly` compiles each component (reusing `compile_design`) and
  **solves** each placement transform from the mates — *the LLM never computes
  transforms*. Bodies are kept **separate** (a real assembly isn't one welded
  solid) and returned as a `cq.Compound`.

**Decomposition is a JUDGMENT (only where needed).** `core/spec.decompose(prompt)`
decides part-vs-assembly INDEPENDENTLY of the planner (so it can't game it), with a
sharp rule (assembly only for ≥2 physically distinct bodies), a deterministic guard
(fewer than 2 components → part), and an offline keyword fallback. Verified:
impeller/bracket/gear → part; AC-unit, enclosure+lid → assembly.

**Phase 2b (DONE) — interface verification (the merge is now a check, not a hope):**
- `verification/interface_inspector.py` (`inspect_interfaces`): per mate, on the
  PLACED bodies — **no unintended interference** (`A∩B` volume ≤ allowance),
  **real contact** (bbox gap ≤ ε, no floating), **concentric alignment**, and
  **fit/clearance** (bore−shaft vs declared fit). Mate-keyed results.
- `verification/assembly_inspector.py` (`inspect_assembly`): runs Phase-1 L2 on
  EACH component (every part independently correct) AND the interface checks (the
  merge correct) → one node-keyed report the reviewer/coverage consume like a part.
- `pipeline.py` routes on the decomposition judgment: monolithic → the part loop;
  assembly → `_run_assembly` (same loop: validate_assembly → compile_assembly →
  inspect_assembly → reviewer → handoff → registry, with REDESIGN repair).

**Still to come:** 2c — per-component Phase-1 coverage + vision-on-the-assembled-
whole + finer interface-targeted repair.

**Why robust:** declaring mates and *solving* placement removes datum mismatch and
tolerance stack-up by construction; interference/contact/fit verify the merge
deterministically. Tested: a lid buried in the box (8000 mm³ overlap) and a
floating lid are both caught.

---

## 9. End-to-end workflow (current)

```
prompt
  → core/spec.extract_spec ............. immutable intent contract (independent)
  → IRPlanner.generate_ir(spec) ........ Geometry IR (Part) or Assembly IR
  → geometry_ir.validate_plan (L1) ..... schema + refs
  → primitives.compile_design .......... IR → solid + provenance (geometry authority)
      (assembly: primitives.compile_assembly → solved multi-body)
  → export STEP/STL
  → verification.inspect_solid (L2) .... deterministic vs declared claims
  → renderer + vision_agent (L3) ....... advisory multimodal
  → (meshlib_agent, L4) ................ only for custom/mesh-only nodes
  → reviewer_agent ..................... APPROVED / REDESIGN(node-keyed) / HALT
  → core.spec.check_coverage ........... intent-coverage gate (APPROVED only if covered)
  → handoff.emit_forgecad_bundle ....... ir.json + stl/step + manifest
  → core.registry ...................... acceptance gate + durable record
```

Provider failover (Claude→Gemini) is automatic everywhere via `core/providers.py`
+ `core/adk_runner.py`.

---

## 10. Status

### Capability-based model routing (core/providers.py)
Each role LEADS with the family best suited to it, and falls back to the other:
- **Claude** → planner + meshlib inspector (precise structured code/IR, strict
  schema, tool use).
- **Gemini Pro** → vision verifier (native multimodal), reviewer (analytical),
  and intent extraction (and intent uses a DIFFERENT family than the planner, so
  the examiner doesn't share the student's blind spots).
- **Gemini Flash** → cheap process/dimension classification.
Swap any of these in one dict; the other family is the automatic fallback.

### Phase 2c (DONE)
- Assembly **coverage gate**: the user SPEC is checked against the *assembled
  whole* (flattened component features), so an assembly can't be APPROVED unless
  intent is covered.
- **Vision on the assembled whole**: the multi-view render of the full assembly is
  judged by the (Gemini) vision verifier — catches gross configuration/orientation
  the numbers miss; advisory to the reviewer.
- **Interface-targeted repair**: the reviewer maps a failed interface check
  (no_interference / contact / concentric_alignment / fit) to a surgical fix, with
  interference ranked highest.

### Phase 3 (DONE) — observability + deterministic eval harness
- `reporting/report.py` → one self-contained **`report.html`** per run (open it to
  SEE: prompt, spec, decomposition, node-keyed check table, coverage, verdict,
  acceptance, and the embedded rendered views). Wired into every pipeline exit.
- `evaluation/` → a curated **edge-case library** (`cases.py`) run through the
  deterministic spine (`run_eval.py`) → a visible **scorecard**
  (`evaluation/report/index.html`) + summary.json. 11 cases incl. interference,
  floating parts, mate cycles, missing-ground, flat-vs-swept, wrong-count,
  too-thick blade, missing param. `python -m evaluation.run_eval`.
- The harness immediately earned its keep: it caught a value-level intent loophole
  (planner asserts count=6 while spec wants 7 → wrongly "covered"). Fixed:
  `check_coverage` now verifies the BUILT measurement matches the SPEC's value
  (not the planner's self-chosen assert).

### Determinism boundary (honest)
- **Deterministic** (and now visibly eval-gated): validation, compiler, L2, interface
  checks, mate-solver, coverage, reporting. Given an IR, correctness is reproducible.
- **Stochastic**: the planner (IR generation), `extract_spec`/`decompose`, and vision
  are LLM calls. The *acceptance criteria* are deterministic; the *creation* is not.

### Phase 4 (DONE) — Product API

**Why.** The engine was CLI-only; an industry-usable platform needs a service
surface (and a backend for the ForgeCAD editable UI). **What.** `api/app.py`
(FastAPI): POST /designs starts a background run, GET status/report/artifacts
expose it. `RUNNER` is swappable so tests run with no LLM. Artifact serving is
path-traversal-safe; an optional `HARNESS_API_KEY` guards every request (open
only when unset, for local dev — full auth is Phase 8). Run with
`uvicorn api.app:app`.

### Phase 4b/4c + Phase 5 (DONE) — control loop over HTTP + the ForgeCAD surface

**4b — iterate/approve.** `POST /designs/{id}/iterate` starts a CHILD run seeded
with the parent prompt + revision feedback (a resumable planner session is Phase 7;
re-run-with-feedback is the pragmatic interim). `POST /designs/{id}/approve` is the
human acceptance gate over HTTP (writes the acceptance record, accepted_by=api).

**4c — live stream.** `WS /ws/designs/{id}/stream` pushes status frames until the
run is terminal — so a UI can watch a run converge.

**Phase 5 — ForgeCAD editable surface.** `api/viewer.py` serves a self-contained
page that renders the run's STL in 3D (three.js) and shows the editable IR;
`api/recompile.py` runs the deterministic spine on an edited IR and returns the
new STL + node-keyed checks. This makes the handoff contract *operable*: edit a
param → recompile server-side → re-verify, all in the browser. The IR JSON is the
one artifact crossing the JS/Python boundary. Verified live on a real bundle.

### Web UI (DONE) — operate everything from the browser

**Why.** The platform was API/CLI-only; users needed one place to drive it.
**What.** `webui/` — a no-build static front-end mounted at `/ui`: a dashboard
(prompt → start run → live run list) and a run page (live WS status + tabs:
Summary = the report, 3D & Edit = the viewer, Actions = iterate/approve). It is
deliberately **thin glue** reusing the API + report + viewer — no duplicated
logic, fully modular under `webui/`. Open `http://localhost:8000/`.

### 'Event loop is closed' + live-logs UI + multi-failure convergence (DONE)

**Problem.** Terminal showed `RuntimeError: Event loop is closed` tracebacks; the
UI 3D tab threw a RangeError and Summary showed raw 404 JSON; and a 4-failure
impeller doom-looped (the planner only ever heard the single most-blocking fix).

**Why (event loop).** ADK opens+closes an asyncio loop per LLM call; the httpx
async client's deferred socket cleanup fires on the closed loop AFTER the response
arrived — a benign teardown race. Our old hook caught only the *unraisable* path,
not the asyncio *task-exception* path.

**Fix.** (1) `core/_quiet.py` now suppresses BOTH paths (unraisablehook + an
`asyncio`-logger filter checking message + exc_info), only for that exact message.
(2) `GET /designs/{id}/log` + a reworked Summary tab show the **live log + an error
panel + the report when ready**; every pipeline exit now writes a report; the 3D tab
gates on the handoff bundle and the viewer guards its fetch. (3) The reviewer now
emits ALL failing node-keyed fixes (most-blocking first), so multi-failure runs
converge instead of looping on one issue.

### API-key bootstrap + browser planner questions (DONE)

**Problem 1 — `.env` looked correct but ADK still reported API-key/model errors.**
The repo documented and used `GEMINI_API_KEY`, and direct `google-genai` calls passed
that value explicitly. ADK's Gemini model path, however, expects the Google AI Studio
key as `GOOGLE_API_KEY` when using string Gemini models. So one path could work while
the ADK planner/reviewer/vision path still behaved like no key existed. A second
fragility was model naming: provider defaults had drifted to preview/non-standard ids
(`gemini-3.1-pro-preview`, `claude-sonnet-4-6`) instead of stable documented API ids.

**Fix.** `core/env.py` is now the single environment bootstrap. It loads the root
`.env`, defaults `GOOGLE_GENAI_USE_VERTEXAI=false`, mirrors
`GEMINI_API_KEY <-> GOOGLE_API_KEY`, and exposes only secret-safe provider presence.
`pipeline.py`, `api/app.py`, `core/providers.py`, and `core/llm_client.py` bootstrap
before resolving models. `core/providers.py` now uses stable defaults
(`gemini-2.5-pro`, `gemini-2.5-flash`, `claude-sonnet-4-20250514`) and supports
per-role overrides (`PLANNER_MODEL`, `INTENT_MODEL`, `VISION_MODEL`, etc.), preserving
the one-file provider swap dial without hard-coding future model changes.

**Problem 2 — the planner could not ask questions from the web UI.** The dashboard
posted only `{prompt}`, so API runs were non-interactive. Even if `interactive=true`
was sent, the planner's `ask_user` tool read from terminal stdin; a FastAPI background
thread has no browser input channel.

**Fix.** The planner remains modular: `IRPlanner(interactive=True,
question_handler=...)` swaps in an `ask_user` tool with the same ADK-facing name and
schema, but backed by a caller-provided handler. The API provides that handler. When
the planner asks, the run state becomes `waiting_for_user`, `/status` and the
websocket expose `pending_question`, and `POST /designs/{id}/answer` resumes the
blocked planner thread. The browser run page shows the question panel and sends the
answer. If no answer arrives before timeout, the handler returns a best-judgment note
instead of deadlocking the run.

**Verification added.** `tests/test_env.py` covers key aliasing and per-role model
overrides. `tests/test_planner.py` covers the injected planner question handler.
`tests/test_api.py` covers the browser wait/answer/resume path, wrong question ids,
and preserves the existing no-LLM API tests.

---

## 20. Post-launch run fixes (surfaced by real end-to-end runs)

### A. "no IR emitted" — planner emits validation message without JSON block
**Problem.** After calling `validate_plan(ir_json)` → `valid: true`, the model returns
"Validation passed." without the JSON block. `safe_parse_json` finds nothing → `None`.
**Fix.** `tools/planner_tools.py::validate_plan` caches the valid IR in thread-local
`_tl.last_valid_ir` and returns `ACTION_REQUIRED` key forcing the model to re-emit it.
`agents/planner_agent/agent.py::extract_ir` falls back to this cache when text parse fails.

### B. `run_review` not defined in `_run_assembly`
**Problem.** `from agents.reviewer_agent import run_review` is a local import inside
`run_pipeline()`. `_run_assembly()` is a module-level function and can't see it → NameError.
**Fix.** Added `from agents.reviewer_agent import run_review` inside `_run_assembly` with
the other local imports.

### C. Iterate prompt corrupts process/spec/decompose
**Problem.** `iterate()` builds: `PRIOR Q&A CONTEXT...\n<design>\n\nREVISION REQUESTED:...`
`detect_process`, `extract_spec`, `decompose` ran on the full string — picking up keywords
from the revision text ("FDM" → wrong process; "fans or side blade" → wrong assembly split).
**Fix.** `pipeline.py::_design_prompt()` strips context blocks and revision suffix before
these three calls. The planner still receives the full prompt.

### D. Spec extractor generates phantom/unverifiable requirements
**Problem.** Gemini 2.5-pro intent extractor invents:
- Abstract targets (`centrifugal_impeller_form`, `smooth_surfaces`) that no IR feature can match
- Derived/inferred dimensions not stated in the prompt (e.g., tip_diameter = 2×hub_radius)
These doom the coverage gate — the run exhausts all 6 attempts and never converges.
**Fix.** `_EXTRACT_INSTRUCTION` now explicitly forbids multi-word abstract targets and
inferred dimensions. `extract_spec()` post-processing drops requirements with:
`feature_present` + multi-word/underscored target, or `dimension` with `expected=null`.

### E. Planner inverts `r_base` / `r_top` for frustum hubs
**Problem.** The planner consistently puts the smaller radius at `r_base` (z=0) and the
larger at `r_top` — building the hub upside-down. Coverage fails on base/top dimension checks
across all 6 redesign attempts because the feedback was not surgical enough.
**Fix.** `PLANNER_INSTRUCTION` now has an explicit FRUSTUM / CONE ORIENTATION section with
the mapping rule and a worked example. `coverage_feedback()` detects the swap pattern
(measured base ≈ expected top and vice versa) and emits a targeted correction message.

### F. Taper assert `true` causes wrong L2 direction check
**Problem.** `_check_taper(node, prov, direction)` when `direction=True` falls to the
`else` (outward_top) branch. A correctly-built impeller hub (wider at base) fails L2 taper
because the wrong direction is tested.
**Fix.** `solid_inspector.py::_check_taper` normalises non-string direction → `"outward_base"`.
`PLANNER_INSTRUCTION` now specifies: always assert `"taper": "outward_base"` (string).

### G. rag_kb2 injection point was wrong
**Problem.** rag_kb2 OCCT error patterns match on Python tracebacks (keywords like
`StdFail_NotDone`) but the injection point was the MeshLib baseline JSON, which never
contains those keywords — so rag_kb2 never actually matched.
**Fix.** `tools/meshlib_tools.py::execute_meshlib_code` now appends KB context to `stderr`
when a sandbox execution fails, so the inspector sees it on the next retry.

### H. 3D viewer blank (STLLoader CDN dep)
**Problem.** The CDN-loaded `THREE.STLLoader` was silently failing; errors in `show()` were
uncaught; fixed camera distance made off-screen models invisible.
**Fix.** `api/viewer.py` now uses an inlined 30-line binary STL parser (no CDN dep), wrapped
in try-catch with error surfacing, dynamic camera distance from bbox diagonal, mouse-drag orbit.

### I. ForgeCAD viewer — parameter sliders
**Problem.** Editing the IR required modifying raw JSON.
**Fix.** `api/viewer.py` adds a `buildParamPanel(ir)` function that generates range slider +
number input pairs for every numeric parameter, with 600ms debounce recompile.

## Status
- Tests: **108/108** — ir(10), primitives(12), solid_inspector(11),
  renderer_vision(5), planner(9), reviewer(8), pipeline(5), forgecad(5),
  spec(9), assembly(15), eval(4), api(15) = 108. Run: `.venv/bin/python tests/test_*.py`.
- Phase 1 (intent) + Phase 2 (assembly) + Phase 3 (observability/eval) +
  Phase 4 (Product API) + Phase 5 (ForgeCAD viewer + sliders) + post-launch hardening (A–I) complete.
  Next: Phase 6 (trace flywheel), 7 (Temporal durability), 8 (hardening/auth).
