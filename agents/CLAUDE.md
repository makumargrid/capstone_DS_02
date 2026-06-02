# agents/ — Design Patterns and Constraints

## Information Asymmetry (Anti-Hallucination)
The **Reviewer agent intentionally never sees the generated CadQuery code**. Its three inputs are:
1. Design brief (user intent + expected dimensions)
2. Static ground truth (deterministic MeshLib results — hard numbers)
3. AI inspector findings (what the inspector agent reported)

When AI findings contradict static results, reviewer trusts static. This design prevents the LLM from rationalizing its own code — it must argue from geometry evidence, not from code it wrote. Do not add the generated code as a fourth input.

## Reviewer Decision Logic
- `APPROVED` — Static checks pass AND AI finds no genuine problems
- `REDESIGN` — Confirmed design problem; must include actionable recommendations for planner
- `HALT` — Contradictory/uninterpretable results requiring human review

Recommendations from `REDESIGN` are sent back to the Planner for the next outer iteration. They must be quantitative where possible ("increase BLADE_T to 2.5mm", not "make walls thicker").

## Subprocess Isolation (meshlib_agent)
`sandbox_executor.py:run_in_sandbox()` runs AI-generated MeshLib code in a subprocess. This is **mandatory**:
- MeshLib C++ bindings SEGFAULT on invalid mesh operations
- SEGFAULT in main process kills the pipeline without a trace
- Subprocess catches exit code -11 (SEGFAULT) and -15 (TIMEOUT) cleanly

`run_invariant_baseline()` runs hardcoded safety checks in the main process before the AI agent generates any code. These are the non-negotiable ground truth checks (watertightness, volume > 0, self-intersections). They never run in the sandbox.

## ADK Session Management
- **Planner**: One persistent session for the entire pipeline run. Maintains context across all outer loop iterations so redesign feedback accumulates.
- **Inspector**: New session per outer iteration. Inspector sees only the current mesh evidence.
- **Reviewer**: New session per outer iteration. Stateless reasoning from three inputs.

Each agent imports `src/model_config.py` indirectly (via `llm.py` or explicit import). Ensure `model_config` is imported first in pipeline.py.

## Agent Tool Availability
| Agent | Tools | Rationale |
|-------|-------|-----------|
| Planner | `ask_user` (interactive mode only) | Asks clarifying questions before generating |
| Inspector | `execute_meshlib_code`, `explore_meshlib_api` | Writes + runs code, discovers API |
| Reviewer | None (pure reasoning) | No tools needed — cross-references provided data |

## Adding a New Agent
1. Create `agents/<name>/agent.py` with `root_agent` (ADK Agent) + `run_<name>()` entry point
2. Create `agents/<name>/__init__.py` exporting both
3. Import `src/model_config` before the agent module in pipeline.py
4. Add phase to `pipeline.py:run_pipeline()` with output JSON saved to `outputs/`
