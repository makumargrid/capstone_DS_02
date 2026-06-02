# Geometry Agent Harness — v1 CAD Pipeline

## What This Is
Multi-agent pipeline: NL prompt → semantic planning → CadQuery geometry → MeshLib validation → adversarial review. Three AI agents (Planner, Inspector, Reviewer) plus deterministic geometry checks. Target: >80% valid first-pass geometry with full audit trail.

Problem statement: [AI_Harness_ForgeCAD_Magazine.html](./AI_Harness_ForgeCAD_Magazine.html) — covers the full architecture decision memo including Temporal, RLM, GRT, ForgeCAD layers, and the Geometry Agent Runtime vision.

## Stack
| Component | Role |
|-----------|------|
| Google ADK | Agent orchestration framework |
| Claude Sonnet 4.6 / Gemini 2.5 Pro | LLM (Claude primary if ANTHROPIC_API_KEY set) |
| CadQuery | Canonical solid generation (Python CAD kernel) |
| MeshLib | Deterministic mesh inspection + repair (C++ bindings) |
| knowledge_base/manufacturing_profiles.json | DFM constraints for 6 processes |

## Pipeline Phases (`pipeline.py:run_pipeline`)
| # | Phase | Decision Point |
|---|-------|---------------|
| 1 | Plan + generate code | Planner agent with process-aware DFM injection |
| 2 | Execute CadQuery | Inner retry loop for syntax/runtime errors |
| 3 | Export STL + STEP | Hard fail if export fails |
| 4 | Static checks | Deterministic: watertight, dims, wall thickness, normals |
| 4b | DFM feedback | Skip AI agents if static already specifies the fix |
| 5 | AI mesh inspection | Inspector agent — findings ONLY, no verdict |
| 6 | Adversarial review | Reviewer cross-references static truth vs AI findings |

Outer loop (max 5): redesign iterations. Inner loop (max 4): syntax/execution retry.

## Critical Invariants — Never Break These
1. **exec() scope** — `cad_executor.py` uses single-dict `exec(scope, scope)`. Two-dict form breaks module-level constants with NameError. This was root fix #1.
2. **Information asymmetry** — Reviewer agent NEVER receives the generated CadQuery code. It only sees design brief + static ground truth + AI inspector findings. Breaking this destroys the anti-hallucination design.
3. **Wall thickness metric** — DFM check uses **p5** (5th percentile), NOT structural_min. Using structural_min caused 5.5× over-rejection. `DFM_TOLERANCE = 0.05mm` is intentional artifact filtering (not a typo).
4. **Import order** — `src/model_config.py` must be imported before any ADK agent is instantiated. It patches the ADK registry to use native Anthropic API instead of Vertex AI.
5. **Subprocess isolation** — MeshLib agent runs AI-generated code in a subprocess. This is mandatory — bad MeshLib calls SEGFAULT. Do not move this into the main process.

## File Map
| File | Role |
|------|------|
| `pipeline.py` | Main orchestrator — outer/inner loops, phase routing, DFM feedback |
| `src/llm.py` | `PlannerAgent` — ADK session, `generate_cad_code()`, `regenerate_with_feedback()` |
| `src/cad_executor.py` | `execute_cad_code()`, `export_solid()` |
| `src/mesh_inspector.py` | Deterministic checks: watertight, dims, wall thickness, normals, degenerate faces |
| `src/process_detector.py` | `detect_process()` — keyword scan → LLM fallback |
| `src/model_config.py` | Model selection + ADK registry patch for Claude |
| `src/logger.py` | `get_agent_logger()` — console + optional file output |
| `agents/meshlib_agent/agent.py` | Inspector ADK agent + `run_inspection()` entry point |
| `agents/meshlib_agent/sandbox_executor.py` | Subprocess wrapper + `run_invariant_baseline()` |
| `agents/reviewer_agent/agent.py` | Adversarial reviewer + `run_adversarial_review()` |
| `knowledge_base/manufacturing_profiles.json` | DFM rules for FDM, SLA, SLS, CNC, Injection Molding, Casting |
| `fix.md` | Honest bug audit — root fixes vs heuristic compensators |

## Active Gotchas (from fix.md)
- Code extraction concatenates ALL python blocks in planner response — fragile if planner adds illustrative snippets
- Z-floor filter (1.5mm in mesh_inspector.py) masks real blade-root thinning — should instead fix via planner prompt
- Loop counts (5 outer, 4 inner) are compensators for upstream bugs — revisit after root fixes stabilize
- `extract_expected_dimensions()` in llm.py is a fallback; primary path is `planner.get_design_dimensions()`

## Outputs Layout
```
outputs/run_YYYYMMDD_HHMMSS/
  00_pipeline_execution.log
  01_design_brief.json
  02_outer{N}_planner_construction_plan.txt
  03_outer{N}_inner{M}_planner_generated_cad_code.py
  04_outer{N}_exported_model.{step,stl}
  05_outer{N}_static_inspection_ground_truth.json
  06a_outer{N}_ai_inspector_findings.json
  06b_outer{N}_ai_inspector_conversation_trace.json
  06c_outer{N}_ai_generated_meshlib_script_{K}.py
  07_outer{N}_adversarial_reviewer_verdict.json
```

## How to Run
```bash
python pipeline.py          # interactive — prompts for design request
# Set ANTHROPIC_API_KEY for Claude; else falls back to GEMINI_API_KEY
```

## Manufacturing Processes Supported
FDM (2.0mm walls) · SLA (0.5mm) · SLS (0.7mm) · CNC (0.5mm, ±0.05mm tolerance) · Injection Molding (1.0mm, 2° draft) · Casting (3.0mm, 3° draft)
