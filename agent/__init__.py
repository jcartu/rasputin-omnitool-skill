"""Agent loop — planner → executor → reviewer with one-shot revise."""
from __future__ import annotations

from typing import Any

from agent.planner import plan, Plan
from agent.executor import execute, ExecutionTrace
from agent.reviewer import review, Review
from agent.tool_registry import load_tools, load_tool_metadata


def run_goal(goal: str) -> dict[str, Any]:
    """Run the full agent loop: plan → execute → review (with one revise attempt).

    Returns a dict with plan, trace, artifacts, and review.
    """
    tools_meta = load_tool_metadata()
    plan_obj = plan(goal, tools_meta)
    tools = load_tools()
    trace = execute(plan_obj, tools)
    artifacts = list(trace.artifacts)
    rev = review(trace, artifacts)

    if rev.verdict == "REVISE":
        # One re-plan attempt
        revised_goal = goal + f"\n\nReviewer findings to address:\n{rev.notes}"
        plan_obj_v2 = plan(revised_goal, tools_meta)
        trace_v2 = execute(plan_obj_v2, tools)
        artifacts_v2 = list(trace_v2.artifacts)
        rev_v2 = review(trace_v2, artifacts_v2)
        return {
            "plan": plan_obj_v2,
            "trace": trace_v2,
            "artifacts": artifacts_v2,
            "review": rev_v2,
            "revised": True,
        }

    return {
        "plan": plan_obj,
        "trace": trace,
        "artifacts": artifacts,
        "review": rev,
        "revised": False,
    }
