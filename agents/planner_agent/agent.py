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
from tools.planner_tools import list_primitives, get_primitive_schema, validate_plan, verify_spatial_placement, ask_user as _terminal_ask_user, get_last_valid_ir

logger = logging.getLogger("planner_agent")

# ═══════════════════════════════════════════════════════════════════════════
# BASE INSTRUCTION — universal for ALL part types (no domain-specific guidance)
# ═══════════════════════════════════════════════════════════════════════════
BASE_PLANNER_INSTRUCTION = """You are a senior CAD engineer. You design parts as a
**Geometry IR** — a typed parametric feature tree in JSON — NOT as free-form code.

## Workflow (follow in order)

### 1. CLARIFY — understand what the user truly needs (before designing)
Your goal is to help ANY user — from engineers to hobbyists — describe what they
want to build. Use `ask_user` for genuinely missing information. Batch ALL questions
into ONE call. Skip this step if the prompt already has enough detail.

QUESTION STYLE — make every user feel understood:
- EXPLAIN WHY you are asking: "I'm asking because this affects how strong the walls
  need to be and what shape will work best for your purpose."
- Use EVERYDAY ANALOGIES, never raw technical parameters:
  "Should this part be lightweight like a plastic phone case, or strong like
   a metal wrench?" — NOT "Specify min_wall_mm and material grade."
- Give 2–3 plain-language options with what each means in practice:
    a) "Basic function — just need the shape to work" (simpler, faster to make)
    b) "Balanced — good strength and finish" (the standard choice for most things)
    c) "Maximum durability — needs to handle stress/heat/wear" (stronger, may cost more)
- ALWAYS end with: "If you're not sure, I'll use the industry standard approach —
  just say 'standard' and I'll handle the details."
- When spatial shape matters, describe it in words first, then offer an ASCII sketch:
    "The blades can curve in different ways. Imagine holding the part:
      a) They sweep backward like a jet engine fan — smooth and efficient
      b) They go straight out like a desk fan — simple and sturdy
      c) They lean forward like a vacuum impeller — more pressure, less stable
    For most rotating parts, option (a) is the standard."
- NEVER use words like 'radial', 'axial', 'frustum', 'parameter', 'tolerance',
  or 'specification' in your question. Talk about what the part DOES, not its math.
- If the user already described their need clearly, proceed to DISCOVER.

### 2. DISCOVER the available building blocks
Call `list_primitives` to see what shapes are available. For each shape you plan
to use, call `get_primitive_schema` so you know the exact names of every dimension.

### 3. PLAN the feature tree
Briefly think through: what's the main body? What gets added to it (unions)?
What gets cut away (holes, pockets)? What repeats in a pattern?

### 4. EMIT the IR as JSON
Build the complete Design and output it as ONE ```json fenced block.

### 5. SELF-CORRECT
Call `validate_plan` on your IR. If it returns errors, fix the exact node it
names and re-validate. Keep fixing until valid=true.

## Universal Rules (apply to EVERY design)
- PREFER LIBRARY PRIMITIVES. Use `custom` ONLY when no primitive can express the
  shape — `custom` blocks are quarantined (not natively editable, fewer checks).
- For N identical features (blades, bolt holes, fins, teeth) use a
  `circular_pattern` or `linear_pattern` — NEVER hand-place N separate copies.
- Declare intent in `asserts` so the deterministic inspector can verify it:
  Pattern's `count`, a feature's `uniform_thickness_mm`, a hub's `taper`
  (string: `"outward_base"` or `"outward_top"`, never boolean `true`),
  a bore's `bore_diameter_mm`.
- Set `envelope` to the overall bounding box of the FINISHED part, INCLUDING
  every feature that sticks out (blades, bosses, fins often extend above/beyond
  the main body). Use `tolerance_mm` of at least 5% of the largest dimension.
  Precise dimensions live in per-feature `asserts`, not in the envelope.

## Frustum / Cone Orientation (when using `cone` / `frustum` primitive)
- `r_base` = radius at z=0 (the PHYSICAL BOTTOM of the part).
- `r_top`  = radius at z=height (the PHYSICAL TOP).
- "base diameter 100mm, top diameter 30mm" → r_base=50, r_top=15. NEVER invert.
- The `taper` assert key must be a STRING: `"outward_base"` (wider at bottom)
  or `"outward_top"` (wider at top). Do NOT use boolean `true`.

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
Custom escape hatch (last resort):
  {"id","type":"custom","params":{"code":"<cadquery; assign result_solid>"}}

## Final output
After validation passes, output the final IR as ONE ```json fenced block.
"""

# ═══════════════════════════════════════════════════════════════════════════
# DOMAIN INSTRUCTIONS — injected only when the part type is detected
# ═══════════════════════════════════════════════════════════════════════════

DOMAIN_ROTATING_BLADED = """
## ROTATING BLADED PART GUIDANCE (impeller / turbine / fan / compressor / propeller)

PRINCIPLE: Every union feature must protrude beyond its parent surface AND maintain
contact with the parent across its full height. The compiler will automatically verify
both `feature_contributes` (is it protruding?) and `parent_contact` (is it attached?).

### CRITICAL: Parent Contact on Tapered Hubs

The hub surface radius CHANGES with height. A vertical blade (lean_deg=0) on a
tapered frustum will DETACH at the top — at z=60mm the hub is only r=15mm wide but
the blade is still at its base position r=40mm. This produces corrupted geometry.

TO FIX: Set lean_deg to track the hub taper so the blade stays in contact:
  lean_deg ≈ arctan((r_base - r_top) / height)
  Example: r_base=50, r_top=15, height=60 → lean_deg ≈ 30°

VERIFY with verify_spatial_placement after setting lean_deg:
- If blade min radius at top falls below bore radius, reduce lean_deg
- For backward-curved (industry standard): twist_deg = -35 to -45
- For straight radial (simple): twist_deg = 0

### Blade Positioning

Before emitting IR, use verify_spatial_placement to check:
- blade must protrude beyond hub at all z-levels
- blade must NOT cross into the bore
- USE ask_user when blade tip radius / outer diameter is not specified
"""

DOMAIN_GEAR = """
## GEAR / SPROCKET GUIDANCE

For gears: use a `circular_pattern` of `box` or `blade` features around a central
`cylinder` hub. Declare tooth count in the pattern's `asserts.count`. The tooth
profile should protrude radially from the hub surface.
"""

DOMAIN_ENCLOSURE = """
## ENCLOSURE / HOUSING / BOX GUIDANCE

For enclosures: use a `box` or `cylinder` as the outer shell. Cut the interior
with a slightly smaller box/cylinder (`op: cut`) to create the hollow cavity.
Wall thickness = (outer_dim - inner_dim) / 2. Add mounting holes, bosses, or
ribs as separate features on the appropriate face.
"""

DOMAIN_BRACKET = """
## BRACKET / MOUNTING PLATE GUIDANCE

For brackets: use a `box` as the base plate. Add `hole` features for mounting
points (often a `linear_pattern` or two holes at known positions). Add ribs
(`box` with small width) for reinforcement where the load is highest.
"""

# Map of prompt keywords → domain instruction to inject
DOMAIN_KEYWORD_MAP: dict[str, str] = {
    "impeller": DOMAIN_ROTATING_BLADED,
    "turbine": DOMAIN_ROTATING_BLADED,
    "compressor": DOMAIN_ROTATING_BLADED,
    "propeller": DOMAIN_ROTATING_BLADED,
    "fan": DOMAIN_ROTATING_BLADED,
    "rotor": DOMAIN_ROTATING_BLADED,
    "pump": DOMAIN_ROTATING_BLADED,
    "screw": DOMAIN_ROTATING_BLADED,
    "auger": DOMAIN_ROTATING_BLADED,
    "turbofan": DOMAIN_ROTATING_BLADED,
    "blade": DOMAIN_ROTATING_BLADED,
    "gear": DOMAIN_GEAR,
    "sprocket": DOMAIN_GEAR,
    "enclosure": DOMAIN_ENCLOSURE,
    "housing": DOMAIN_ENCLOSURE,
    "case": DOMAIN_ENCLOSURE,
    "box": DOMAIN_ENCLOSURE,
    "shell": DOMAIN_ENCLOSURE,
    "container": DOMAIN_ENCLOSURE,
    "bracket": DOMAIN_BRACKET,
    "mount": DOMAIN_BRACKET,
    "plate": DOMAIN_BRACKET,
    "flange": DOMAIN_BRACKET,
}


def _detect_domains(prompt: str) -> str:
    """Scan the prompt for domain keywords; return concatenated domain instructions."""
    pl = prompt.lower()
    injected = set()
    instructions = []
    for keyword, block in DOMAIN_KEYWORD_MAP.items():
        if keyword in pl and block not in injected:
            instructions.append(block)
            injected.add(block)
    return "\n".join(instructions)


def _build_instruction(prompt: str) -> str:
    """Build the full planner instruction: base + domain-specific blocks + relevant CadQuery examples."""
    instruction = BASE_PLANNER_INSTRUCTION
    domain = _detect_domains(prompt)
    if domain:
        instruction += "\n" + domain
    # Append relevant CadQuery API examples from rag_kb1 for the detected domain
    try:
        from rag_kb1 import get_api_context
        kb1 = get_api_context(None, prompt)
        if kb1:
            instruction += "\n\n## Relevant CadQuery API Reference\n" + kb1
    except Exception:
        pass
    return instruction

PLANNER_TOOLS = [list_primitives, get_primitive_schema, validate_plan, verify_spatial_placement, _terminal_ask_user]


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
    instruction=BASE_PLANNER_INSTRUCTION,
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
                 reuse_session_id: str | None = None, prompt: str = ""):
        self.interactive = interactive
        self.process = process
        self.model_name = get_model_name("planner")
        self.fallback_model = get_fallback_model_name("planner")
        ask_tool = _make_ask_user_tool(question_handler)
        self._tools = [list_primitives, get_primitive_schema, validate_plan, verify_spatial_placement, ask_tool] if interactive else [t for t in PLANNER_TOOLS if t is not _terminal_ask_user]
        # _log defaults to the module logger; pipeline.py replaces it with the
        # run-specific file logger (planner._log = log) so all planner activity
        # appears in 00_pipeline_execution.log alongside the pipeline's own logs.
        self._log = logger
        # Build the instruction with domain-specific blocks detected from the prompt
        self._instruction = _build_instruction(prompt)

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

    def _build(self, model: str, instruction: str | None = None):
        """(Re)build agent + runner for `model`. ADK resolves the provider at
        build time, so switching providers requires rebuilding, not mutating.
        `instruction` overrides the base instruction (used for domain injection)."""
        instr = instruction or self._instruction
        self.agent = Agent(model=model, name="planner_agent",
                           description=root_agent.description,
                           instruction=instr, tools=self._tools)
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
