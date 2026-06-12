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
from tools.planner_tools import list_primitives, get_primitive_schema, validate_plan, verify_spatial_placement, _ask_user_terminal as _terminal_ask_user, get_last_valid_ir

logger = logging.getLogger("planner_agent")

# ═══════════════════════════════════════════════════════════════════════════
# BASE INSTRUCTION — loaded from skills/planner/SKILL.md
# ═══════════════════════════════════════════════════════════════════════════
import os as _os
_SKILL_DIR = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))), "skills", "planner")
with open(_os.path.join(_SKILL_DIR, "SKILL.md")) as _f:
    BASE_PLANNER_INSTRUCTION = _f.read()

# ═══════════════════════════════════════════════════════════════════════════
# PLANNER INSTRUCTION BUILDER — base + optional CadQuery API reference
# ═══════════════════════════════════════════════════════════════════════════

def _build_instruction(prompt: str) -> str:
    """Build the full planner instruction: base + relevant CadQuery examples."""
    instruction = BASE_PLANNER_INSTRUCTION
    # Append relevant CadQuery API examples from rag_kb1
    try:
        from knowledge.cadquery_api import get_api_context
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

with open(_os.path.join(_SKILL_DIR, "ASSEMBLY.md")) as _f:
    ASSEMBLY_ADDENDUM = _f.read()

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
