"""Executor router for static vs ReAct execution modes."""
from __future__ import annotations

import os
from typing import Any, Callable

from agent.config import CONFIG
from agent.executor import ExecutionTrace, execute as static_execute
from agent.planner import Plan


def current_mode() -> str:
    """Return the selected executor mode; ReAct is the default."""
    mode = os.environ.get("RASPUTIN_OMNITOOL_EXECUTOR_MODE", CONFIG.executor_mode)
    return "static" if mode.lower() == "static" else "react"


def execute(
    plan: Plan,
    tools: dict[str, Callable],
    context: dict[str, Any] | None = None,
) -> ExecutionTrace:
    """Execute a plan using the configured executor mode."""
    if current_mode() == "static":
        return static_execute(plan, tools, context)

    from agent.react_executor import react_execute
    from agent.tool_registry import load_tool_metadata

    tool_metadata = load_tool_metadata()
    return react_execute(
        plan.goal,
        tools,
        tool_metadata,
        plan_hint=plan,
        max_steps=CONFIG.max_steps_per_goal,
        budget_usd=CONFIG.max_goal_cost_usd,
        max_wallclock_min=CONFIG.max_wallclock_per_goal_min,
        soft_cap_tokens=CONFIG.soft_cap_tokens,
    )
