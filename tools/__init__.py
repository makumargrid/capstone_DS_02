"""
tools/ — ALL agent tools in one place, grouped by the agent that registers them.

  planner_tools.py   → agents/planner_agent : list_primitives, get_primitive_schema,
                       validate_plan, ask_user.
  meshlib_tools.py   → agents/meshlib_agent : execute_meshlib_code,
                       explore_meshlib_api (+ set_run_context, run-dir routing).
  meshlib_sandbox.py   subprocess isolation helper used by meshlib_tools.

Agents register tools via `Agent(tools=[...])`; ADK derives each tool's schema
from its function signature + docstring. The Vision Verifier and Reviewer agents
use NO function-tools (images/text go in the message), so they have no entry here.
"""
