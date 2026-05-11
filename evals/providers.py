"""Promptfoo Python provider that wraps agent.run_goal.

Promptfoo invokes this with a prompt + config, expects a response.
For us, the prompt is the goal; the response is run_goal's output (serialized).
"""
from __future__ import annotations

import json
import os
import traceback


def call_api(prompt: str, options: dict, context: dict) -> dict:
    """Promptfoo provider entry point.

    Args:
        prompt: the goal string
        options: provider config (e.g., max_cost, mode)
        context: promptfoo metadata (test name, etc.)

    Returns:
        {"output": "<serialized result>"} on success
        {"error": "..."} on failure
    """
    config = options.get("config", {})
    mode = config.get("mode", "execute")  # "plan-only" | "execute" | "execute-mocked"
    max_cost = config.get("max_cost_usd", "0.50")

    os.environ["RASPUTIN_OMNITOOL_MAX_COST_USD"] = str(max_cost)

    try:
        if mode == "plan-only":
            from agent.planner import plan
            from agent.tool_registry import load_tool_metadata

            tools_meta = load_tool_metadata()
            result = plan(prompt, tools_meta)
            return {"output": json.dumps({
                "mode": "plan-only",
                "task_count": len(result.tasks),
                "tools_referenced": sorted(set(t.tool for t in result.tasks if t.tool)),
            })}
        elif mode == "execute-mocked":
            from agent import run_goal
            os.environ["RASPUTIN_OMNITOOL_MOCK_TOOLS"] = "true"
            result = run_goal(prompt)
            return {"output": json.dumps(_serialize(result))}
        else:
            from agent import run_goal
            result = run_goal(prompt)
            return {"output": json.dumps(_serialize(result))}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"}


def _serialize(result: dict) -> dict:
    """Promptfoo expects JSON-serializable output. Flatten any non-trivial objects."""
    out = {
        "goal_id": result.get("goal_id"),
        "halted": result.get("halted", False),
    }
    if "review" in result:
        review = result["review"]
        out["verdict"] = getattr(review, "verdict", str(review))
        out["review_notes"] = getattr(review, "notes", "")
    if "results" in result:
        out["task_count"] = len(result["results"])
    if "details" in result:
        out["details"] = result["details"]
    if "reason" in result:
        out["reason"] = result["reason"]
    return out
