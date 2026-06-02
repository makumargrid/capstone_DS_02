"""
Planner Agent — emits a validated Geometry IR (not free-form CadQuery).

This replaces the legacy free-form code planner. The agent plans in the typed
primitive library and outputs a Geometry IR JSON. Tools are registered the ADK
way — plain functions passed to `Agent(tools=[...])`; ADK derives each tool's
schema from its signature + docstring (see tools/planner_tools.py).

ROLE: planning. TOOLS: tools/planner_tools.py. CALLED BY: pipeline.py.
CALLS: core/model_config.py, geometry_ir+primitives (via the tools).

`root_agent` is the module-level agent (also usable in `adk web`). `IRPlanner`
wraps it with a persistent session (context across redesign iterations), a
Claude→Gemini provider fallback, and IR extraction. It is the runtime the
pipeline uses.
"""
from __future__ import annotations
import os
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "false")

import json
import uuid
import asyncio
import logging

from google.adk.agents.llm_agent import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from core.model_config import get_model_name, get_fallback_model_name, safe_parse_json
from tools.planner_tools import list_primitives, get_primitive_schema, validate_plan, ask_user as _terminal_ask_user, get_last_valid_ir

logger = logging.getLogger("planner_agent")

PLANNER_INSTRUCTION = """You are a senior CAD engineer. You design parts as a
**Geometry IR** — a typed parametric feature tree in JSON — NOT as free-form code.

## Workflow (follow in order)
1. CLARIFY (ask ALL unknown questions BEFORE starting the design):
   Identify every dimension, shape choice, or functional requirement the user has
   NOT stated. Batch ALL of them into a SINGLE structured question using `ask_user`
   — ask them sequentially in one call. Never stop mid-design to ask.

   QUESTION STYLE — follow exactly:
   - Lead with the USE CASE, not the technical parameter.
     "What will this fan be used for?" not "Specify the application domain."
   - Give 2–4 named options with real-world analogies:
       a) Like a desk fan — moves lots of air gently (low pressure, high flow)
       b) Like a turbocharger — forces air under high pressure (high pressure, lower flow)
       c) Like a building HVAC fan — balanced flow and pressure
   - Include an ASCII diagram when spatial shape matters:
       SIDE VIEW — which blade profile fits your goal?
         a) Curved backward (most efficient, industry standard):   / / /
         b) Straight radial (simpler, more robust):                | | |
         c) Curved forward (higher pressure, less stable):         \ \ \
   - Always state the INDUSTRY STANDARD recommendation explicitly before listing
     options: "For centrifugal compressors, option (a) is the standard — used in
     jet engines, turbochargers, and industrial blowers."
   - Never recommend the easiest-to-build option over the correct one.
   - If the user already provided sufficient detail, skip ask_user and proceed.

   Default questions to ask when designing rotating bladed parts (if not stated):
   - Intended application / working fluid (air, water, fuel — determines blade shape)
   - Performance priority: efficiency, pressure rise, or flow rate
   - Any unspecified key dimensions (tip radius, bore, blade count if not in prompt)
   - Aesthetics importance (functional rough part vs. precision visible surface)

2. DISCOVER: call `list_primitives`, then `get_primitive_schema` for each
   primitive you intend to use, so every param name/type is correct.
3. PLAN: briefly decompose the part into features (base solid, then unions/cuts).
4. EMIT IR: produce ONE JSON object (the Design).
5. SELF-CORRECT: call `validate_plan` on your IR. If it returns errors, fix the
   exact node it names and re-validate until valid=true.

## Rules that make designs verifiable (important)
- PREFER LIBRARY PRIMITIVES. Use `custom` ONLY when no primitive can express the
  shape — it is quarantined (not natively editable, fewer checks).
- For N identical features (blades, bolt holes, fins, teeth) use a
  `circular_pattern` or `linear_pattern` — NEVER hand-place N copies.
- Declare intent in `asserts` so the deterministic inspector can verify it:
  e.g. a pattern's `count`, a feature's `uniform_thickness_mm`, a hub's `taper`
  ('outward_base'/'outward_top'), a bore's `bore_diameter_mm`.
- Set `envelope` to the overall bounding box of the FINISHED ASSEMBLY,
  INCLUDING every feature that protrudes beyond the main body (curved/twisted
  blades, bosses, fins often extend above/around the hub). The envelope is a
  COARSE bound: use `tolerance_mm` of at least 5% of the largest dimension (more
  for swept/curved/twisted parts). Precise dimensions live in `asserts`.

## FRUSTUM / CONE ORIENTATION (critical — do not invert)
`r_base` = radius at z=0 (the PHYSICAL BOTTOM of the part, i.e. the `at` position).
`r_top`  = radius at z=height (the PHYSICAL TOP).
ALWAYS r_base > r_top for parts that are wider at the bottom (standard impellers, hubs).
"base diameter 100mm, top diameter 30mm" → r_base=50, r_top=15. NEVER invert these.
`taper` assert: ALWAYS use the STRING `"outward_base"` (wider at bottom) or
`"outward_top"` (wider at top). Do NOT use `true` — the inspector needs the direction.
Example correct assert: `"asserts": {"taper": "outward_base", "base_diameter_mm": 100, ...}`

## IMPELLER / TURBINE / FAN BLADE GEOMETRY (critical — read carefully)
When designing circular_pattern blades on a tapered hub (frustum/cone), the blade
must be positioned to EXTEND OUTWARD FROM the hub surface, not float inside it.

Correct blade positioning formula:
  r_hub_avg  = (hub.r_base + hub.r_top) / 2        ← average hub radius
  r_tip      = desired tip radius (usually ≥ hub.r_base for centrifugal)
  blade.at[0] = (r_hub_avg + r_tip) / 2             ← blade center = midpoint of span
  blade.chord = r_tip - r_hub_avg                    ← radial span of the blade

Example for hub r_base=50, r_top=15, tip radius=50:
  r_hub_avg = (50+15)/2 = 32.5
  blade.at[0] = (32.5 + 50) / 2 = 41.25  ← NOT 35 or 40
  blade.chord = 50 - 32.5 = 17.5          ← NOT 25

Blade height: set to the HUB height (or slightly less). blade.at[2] = 0.

For centrifugal impellers (backward-curved, industry standard):
  twist_deg = -35 to -45  (negative = backward-curved = more efficient)
  lean_deg  = arctan((hub.r_base - hub.r_top) / hub.height) in degrees
              This angles the blade to track the hub taper, reducing geometric artifacts.
  Example for r_base=50, r_top=15, height=60:
              lean_deg = arctan(35/60) ≈ 30.3°

For axial fans (blades parallel to axis): lean_deg = 0, twist_deg = 15–25.
For radial blades (simple, less efficient): twist_deg = 0, lean_deg = 0.

## IR shape
{
  "version": "1.0", "units": "mm", "process": "<FDM|SLA|CNC|...>",
  "envelope": {"x_mm","y_mm","z_mm","tolerance_mm"},
  "features": [
    {"id","type","params":{...},"op":"union|cut","target":<prior id|null>,
     "asserts":{...optional...}}
  ]
}
Pattern feature shape:
  {"id","type":"circular_pattern","op":"union","target":<base id>,
   "params":{"count":N,"axis":[0,0,1],"feature":{"id","type","params":{...}}},
   "asserts":{"count":N, ...}}
Custom escape hatch:
  {"id","type":"custom","params":{"code":"<cadquery; assign result_solid>"}}

## Final output
After validation passes, output the final IR as ONE ```json fenced block.
"""

PLANNER_TOOLS = [list_primitives, get_primitive_schema, validate_plan, _terminal_ask_user]


def _make_ask_user_tool(question_handler):
    if question_handler is None:
        return _terminal_ask_user

    def ask_user(question: str) -> str:
        """Ask the user one clarifying question about a genuinely ambiguous, critical
        requirement (key dimension, count, tolerance). Use judgment for minor details.

        Args:
            question: the specific question.
        Returns the user's answer, or a proceed-note when no answer arrives.
        """
        return question_handler(question)

    return ask_user

ASSEMBLY_ADDENDUM = """
THIS REQUEST IS AN ASSEMBLY of physically DISTINCT bodies. Emit an ASSEMBLY IR
(NOT a single part):
{
  "version":"1.0","units":"mm","process":"<...>","kind":"assembly",
  "components":[ {"id":"<role>","grounded":true|false,"design":<a full Part IR>} ],
  "mates":[ {"type":"stack_on|concentric|coincident_face|custom","a":"<id>","b":"<id>","params":{...}} ]
}
Rules:
- Each component.design is a normal Part IR (the SAME schema you use for parts,
  with its own features + asserts). Build each component in its OWN local frame
  (base-centered at origin, +Z up).
- Exactly ONE component is "grounded": true. Every other component must be joined
  by a mate, forming a connected tree (no floating parts, no cycles).
- DECLARE mate INTENT — do NOT compute transforms. The compiler solves placement:
    stack_on  : b sits on a's top face, centered.
    concentric: b's axis aligns to a's (e.g. shaft in bore); params {z_offset, bore_mm, shaft_mm, fit}.
    coincident_face: like stack_on with params {gap}.
    custom    : params {translate:[x,y,z]} (last resort).
- Components must NOT interfere (overlap) unless an interference fit is declared,
  and each must actually touch its mate partner.
Output the final ASSEMBLY IR as ONE ```json block.
"""

root_agent = Agent(
    model=get_model_name("planner"),
    name="planner_agent",
    description="Senior CAD engineer that emits a validated Geometry IR feature tree.",
    instruction=PLANNER_INSTRUCTION,
    tools=PLANNER_TOOLS,
)


def extract_ir(text: str) -> dict | None:
    """Extract the IR JSON from the agent's final message.

    Primary: parse the JSON block from the text response.
    Fallback: use the IR that was cached by validate_plan when the model emits
    only 'Validation passed.' and omits the JSON block from its reply.
    """
    ir = safe_parse_json(text)
    if ir is not None:
        return ir
    cached = get_last_valid_ir()
    if cached is not None:
        logger.info("extract_ir: model omitted JSON block — recovered from validate_plan cache")  # module logger; pipeline log via _log
    return cached


class IRPlanner:
    """Persistent-session wrapper used by the pipeline.

    session_db_uri: if provided, uses ADK DatabaseSessionService (SQLite) so the
    conversation is persisted to disk. This lets iterate() reuse the parent run's
    session — the planner sees its full prior history (tool calls, designs, redesigns).

    reuse_session_id: if provided, the planner joins an existing session (no new
    session is created). Used by iterate to resume from the approved run's context.
    """

    def __init__(self, interactive: bool = False, process: str = "FDM",
                 question_handler=None, session_db_uri: str | None = None,
                 reuse_session_id: str | None = None):
        self.interactive = interactive
        self.process = process
        self.model_name = get_model_name("planner")
        self.fallback_model = get_fallback_model_name("planner")
        ask_tool = _make_ask_user_tool(question_handler)
        self._tools = [list_primitives, get_primitive_schema, validate_plan, ask_tool] if interactive else PLANNER_TOOLS[:-1]
        # _log defaults to the module logger; pipeline.py replaces it with the
        # run-specific file logger (planner._log = log) so all planner activity
        # appears in 00_pipeline_execution.log alongside the pipeline's own logs.
        self._log = logger

        if session_db_uri:
            from google.adk.sessions import DatabaseSessionService
            self.session_service = DatabaseSessionService(db_url=session_db_uri)
        else:
            self.session_service = InMemorySessionService()

        if reuse_session_id:
            # Reuse an existing session — the planner inherits full prior history.
            self.session_id = reuse_session_id
            # No create_session call: the session already exists in the DB.
        else:
            self.session_id = str(uuid.uuid4())
            async def _mk():
                await self.session_service.create_session(
                    app_name="planner_agent", user_id="user", session_id=self.session_id)
            asyncio.run(_mk())

        self._build(self.model_name)

    def _build(self, model: str):
        """(Re)build agent + runner for `model`. ADK resolves the provider at
        build time, so switching providers requires rebuilding, not mutating."""
        self.agent = Agent(model=model, name="planner_agent",
                           description=root_agent.description,
                           instruction=PLANNER_INSTRUCTION, tools=self._tools)
        self.runner = Runner(agent=self.agent, app_name="planner_agent",
                             session_service=self.session_service)

    def _invoke(self, message: str) -> str:
        self._log.info(f"[planner] invoking model={self.agent.model}")
        content = types.Content(role="user", parts=[types.Part(text=message)])
        events = list(self.runner.run(user_id="user", session_id=self.session_id,
                                      new_message=content))
        for ev in events:
            if ev.is_final_response() and ev.content and ev.content.parts:
                return ev.content.parts[0].text or ""
        self._log.warning("[planner] no final_response event — ADK runner returned nothing")
        return ""

    def _run(self, message: str) -> str:
        """Invoke the planner; fall back to the other provider if the primary
        raises OR returns no text (ADK logs model errors and yields no final
        response, so an empty result also means the provider failed)."""
        try:
            text = self._invoke(message)
        except Exception as e:
            text, err = "", e
        else:
            err = None
        if not text.strip() and self.fallback_model:
            self._log.warning(f"Planner primary model unavailable ({err or 'empty response'}); "
                              f"falling back to {self.fallback_model}")
            self._build(self.fallback_model)
            self.fallback_model = None
            text = self._invoke(message)
        elif not text.strip() and err is not None:
            raise err
        return text

    def generate_ir(self, prompt: str, spec: list | None = None) -> tuple[str, dict | None]:
        """Plan a part from a prompt. `spec` (if given) is the IMMUTABLE acceptance
        contract: the IR must cover every requirement (name features by their
        `target` role; declare matching asserts). Returns (full_text, ir_or_None)."""
        contract = ""
        if spec:
            import json as _json
            contract = ("ACCEPTANCE SPEC — your IR MUST satisfy EVERY requirement below "
                        "(you may not weaken or drop any). Name each feature by its "
                        "`target` role and declare the matching asserts:\n"
                        + _json.dumps(spec, indent=2) + "\n\n")
        full = self._run(f"{contract}Design request (process={self.process}): {prompt}")
        return full, extract_ir(full)

    def generate_assembly(self, prompt: str, spec: list | None = None,
                          components: list | None = None) -> tuple[str, dict | None]:
        """Emit an Assembly IR (distinct bodies + declared mates). Returns (text, asm_or_None)."""
        import json as _json
        contract = ""
        if spec:
            contract += ("ACCEPTANCE SPEC (must be covered):\n" + _json.dumps(spec, indent=2) + "\n\n")
        if components:
            contract += ("Decompose into these components:\n" + _json.dumps(components, indent=2) + "\n\n")
        full = self._run(ASSEMBLY_ADDENDUM + "\n" + contract
                         + f"Design request (process={self.process}): {prompt}")
        return full, extract_ir(full)

    def revise_assembly(self, feedback: str) -> tuple[str, dict | None]:
        """Apply node-keyed assembly feedback; re-emit the full Assembly IR."""
        full = self._run("REVISION REQUIRED for the ASSEMBLY. Apply ONLY the change below, "
                         "keep the assembly schema, and output the full corrected ASSEMBLY IR "
                         f"as ONE json block.\n\n{feedback}")
        return full, extract_ir(full)

    def revise_ir(self, feedback: str) -> tuple[str, dict | None]:
        """Send node-keyed repair feedback; returns (full_text, ir_dict_or_None)."""
        full = self._run(
            "REVISION REQUIRED. Apply ONLY the change below to your current IR, "
            "re-validate with validate_plan and if required take user into the loop if any confusion is there by callling the ask_user tool, and output the full corrected IR as "
            f"ONE json block.\n\n{feedback}")
        return full, extract_ir(full)
