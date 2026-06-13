# Geometry Agent Harness — v3 IR-Centric CAD Pipeline

## What This Is
IR-centric agentic CAD pipeline: NL prompt → intent resolution → parametric Geometry IR → deterministic CadQuery compilation → multi-layer verification (L2 deterministic, L3 vision advisory, L4 MeshLib) → adversarial review → ForgeCAD handoff bundle with certificate.

Three AI agents (Planner, Vision Verifier, Reviewer) are constrained by deterministic geometry checks that form the ground truth. Vision is advisory only — it can never override a deterministic result.

## Stack
| Component | Role |
|-----------|------|
| Google ADK | Agent orchestration framework |
| Claude Sonnet 4 / Gemini 2.5 Pro | Multi-model (capability-routed per role via `core/providers.py`) |
| CadQuery | Deterministic solid generation from IR (Python CAD kernel) |
| MeshLib | Mesh inspection + repair (C++ bindings) |
| config/process/manufacturing_profiles.json | DFM constraints for 6 processes |
| config/primitives/*.yaml | One YAML per primitive type (8 leaf primitives) |
| skills/*.md | Agent skill files (planner, vision, reviewer) |

## Pipeline Phases (`pipeline.py:run_pipeline`)
| # | Phase | Decision Point |
|---|-------|---------------|
| 0 | Intent Resolution | Extract spec from prompt, ground with standards, confirm |
| 1 | IR Planning | Planner agent emits typed Geometry IR (JSON feature tree) |
| 1b | L1 Validation | Schema + constraint validation of the IR |
| 2 | Compilation | Deterministic CadQuery compilation with provenance audit |
| 3 | Export | STL + STEP export |
| 4 | L2 Inspection | Deterministic: structural checks + DFM checks |
| 5 | L3 Vision | Advisory multimodal verification (rendered views) |
| 5b | L4 MeshLib | Mesh-level inspection for custom/mesh_only nodes |
| 6 | Reviewer | Synthesizes L2 ground truth + L3 advisory → PASS/REDESIGN/HALT |
| 7 | Handoff | ForgeCAD bundle with certificate, trust label, viewer |

## Verdict Contract (critical — do not change without updating oracle)
- `geometrically_valid` (bool): structural/intent checks only (blocking severity)
- `manufacturable` (bool): DFM checks only for the active process (dfm severity)
- `valid` (bool): backwards-compat == `geometrically_valid`
- Every check tagged `severity: "blocking" | "dfm"`
- Certificate reports BOTH flags; never claims certified when `manufacturable=False`

## Critical Invariants — Never Break These
1. **Deterministic-first** — L2 checks run without any LLM. The reviewer's verdict is computed from L2 results. Vision (L3) is advisory only and can NEVER override a passing L2 check.
2. **Information asymmetry** — Reviewer agent NEVER receives generated code. It only sees spec + L2 ground truth + L3 advisory findings.
3. **Registry guard** — `set(LEAF_BUILDERS) == {cylinder, cone, frustum, box, hole, sphere, tube, profile}`. Removing a YAML crashes import with ImportError (loud guard, not silent shrinkage).
4. **Oracle is frozen** — `tests/test_acceptance_groundtruth.py` asserts what is TRUE by construction. Never weaken an assertion; fix the code instead.
5. **Sandbox isolation** — Custom code runs in subprocess with network blocked (socket guard), credentials stripped, and wall-clock timeout. Docstring matches enforced behavior.
6. **Anchor vocabulary** — `_face_point` raises ValueError on unknown face names. Valid: `bottom_center`, `top_center`, `center`.

## File Map (v3 layout)
| Directory | Role |
|-----------|------|
| `pipeline.py` | Main orchestrator — outer loop, phase routing, gates |
| `core/` | Runtime: `env.py`, `providers.py`, `llm_client.py`, `process_detector.py`, `sandbox.py`, `spec.py`, `intent_resolver.py`, `standards.py`, `config_loader.py` |
| `primitives/` | Builders, compiler, registry, anchoring, param models |
| `verification/` | `solid_inspector.py` (L2), `invariants.py`, `dfm.py`, `renderer.py` |
| `config/` | YAML configs: `primitives/`, `process/`, `inspection_thresholds.yaml` |
| `skills/` | Agent skill files: `planner/SKILL.md`, `vision/SKILL.md`, `reviewer/SKILL.md` |
| `knowledge/` | Knowledge corpus for agents |
| `agents/` | ADK agents: `planner_agent`, `reviewer_agent`, `vision_agent` |
| `handoff/` | ForgeCAD bundle emitter + interactive viewer |
| `tests/` | Unit/integration tests including frozen ground-truth oracle |

## Outputs Layout
```
outputs/run_YYYYMMDD_HHMMSS/
  00_pipeline_execution.log
  01_intent_resolution.json
  01b_spec.json
  01_design_brief.json
  01c_decomposition.json
  02_outer{N}_planner_output.txt
  03_outer{N}_ir.json
  04_outer{N}_model.{step,stl}
  05_outer{N}_static_inspection_ground_truth.json
  06a_outer{N}_rendered_views/*.png
  06b_outer{N}_vision_findings.json
  07_outer{N}_adversarial_reviewer_verdict.json
  forgecad_bundle/manifest.json
```

## How to Run
```bash
# Docker (recommended)
docker build -t agentic-cad-pipeline .
docker run --env-file .env -v "$(pwd)/outputs:/app/outputs" agentic-cad-pipeline python pipeline.py "<prompt>"

# Local (requires CadQuery, MeshLib, ADK, provider SDKs)
python pipeline.py "<prompt>"
python pipeline.py --interactive "<prompt>"
```

## Manufacturing Processes Supported
FDM (2.0mm walls, 45° overhang, 30mm bridge) · SLA (0.5mm) · SLS (0.7mm) · CNC (0.5mm, ±0.05mm) · Injection Molding (1.0mm, 2° draft) · Casting (3.0mm, 3° draft)
