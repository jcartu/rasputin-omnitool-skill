"""Executor — walks a Plan, dispatches one tool call per turn, halts on budget."""
from __future__ import annotations

import re
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from agent.planner import Plan
from agent.observability import observe


@dataclass
class ExecutionTrace:
    """Trace of a plan execution."""
    plan: Plan
    steps: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    halted_for: str | None = None


@observe("executor.execute")
def execute(
    plan: Plan,
    tools: dict[str, Callable],
    context: dict[str, Any] | None = None,
) -> ExecutionTrace:
    """Execute a plan by dispatching tool calls one at a time.

    Returns an ExecutionTrace with all steps, artifacts, and halt reason.
    """
    from agent.config import CONFIG
    from agent.observability import set_goal_id

    set_goal_id()
    trace = ExecutionTrace(plan=plan)
    previous_results: dict[str, Any] = {}
    step_count = 0
    failure_count = 0
    started_at = time.time()

    for task in plan.tasks:
        # Halt conditions
        step_count += 1
        elapsed_min = (time.time() - started_at) / 60

        if step_count > CONFIG.max_steps_per_goal:
            trace.halted_for = "MAX_STEPS"
            break
        if step_count > 1 and (failure_count / step_count) > CONFIG.max_tool_failure_rate:
            trace.halted_for = "TOOL_FAILURE_RATE"
            break
        if elapsed_min > CONFIG.max_wallclock_per_goal_min:
            trace.halted_for = "WALLCLOCK"
            break

        # Substitute placeholders in inputs
        inputs = _substitute_placeholders(task.inputs, previous_results)

        # Dispatch tool
        tool_name = task.tool
        if tool_name not in tools:
            failure_count += 1
            trace.steps.append({
                "task_id": task.id,
                "tool": tool_name,
                "status": "error",
                "error": f"Tool '{tool_name}' not found in registry",
            })
            continue

        try:
            result = tools[tool_name](inputs)
            step_result = {
                "task_id": task.id,
                "tool": tool_name,
                "status": "ok" if "result" in result else "error",
                "inputs": inputs,
                "output": result,
            }

            if "result" in result:
                previous_results[task.id] = result["result"]
                # Collect artifact paths
                for key in ("path", "audio_path", "image_path", "video_path"):
                    if key in result["result"] and result["result"][key]:
                        trace.artifacts.append(result["result"][key])
                if "artifacts" in result["result"]:
                    for a in result["result"]["artifacts"]:
                        if isinstance(a, dict) and "path" in a:
                            trace.artifacts.append(a["path"])
                        elif isinstance(a, str):
                            trace.artifacts.append(a)
            else:
                failure_count += 1
                previous_results[task.id] = None

            trace.steps.append(step_result)
        except Exception as e:
            failure_count += 1
            trace.steps.append({
                "task_id": task.id,
                "tool": tool_name,
                "status": "error",
                "error": str(e),
            })

    return trace


def _substitute_placeholders(
    obj: Any,
    previous_results: dict[str, Any],
) -> Any:
    """Recursively substitute ${T1} and ${T1.key} placeholders in inputs."""
    if isinstance(obj, str):
        def _replace(match: re.Match) -> str:
            ref = match.group(1)
            if "." in ref:
                task_id, key = ref.split(".", 1)
                result = previous_results.get(task_id, {})
                if isinstance(result, dict):
                    val = result.get(key, match.group(0))
                    return json.dumps(val) if isinstance(val, (dict, list)) else str(val)
            else:
                result = previous_results.get(ref, match.group(0))
                return json.dumps(result) if isinstance(result, (dict, list)) else str(result)
            return match.group(0)

        return re.sub(r"\$\{([^}]+)\}", _replace, obj)
    elif isinstance(obj, dict):
        return {k: _substitute_placeholders(v, previous_results) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_substitute_placeholders(v, previous_results) for v in obj]
    return obj
