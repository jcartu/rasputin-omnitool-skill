"""Executor — walks a Plan, dispatches one tool call per turn, halts on budget."""
from __future__ import annotations

import re
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from agent.artifact_registry import ArtifactNotFound, RegistryError, get_registry
from agent.planner import Plan
from agent.observability import observe


@dataclass
class ExecutionTrace:
    """Trace of a plan execution."""
    plan: Plan
    steps: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    halted_for: str | None = None
    final_answer: str | None = None

    def artifact_paths(self) -> list[str]:
        """Return artifact file paths, resolving registry IDs when possible."""
        registry = get_registry()
        paths: list[str] = []
        for artifact_id in self.artifacts:
            try:
                paths.append(registry.get(artifact_id).path)
            except (ArtifactNotFound, RegistryError):
                paths.append(artifact_id)
        return paths


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
    goal_id = str((context or {}).get("goal_id") or (context or {}).get("_goal_id") or "ad-hoc")
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
                # Collect artifacts with automatic lineage wiring
                derived_from = _resolve_lineage(task.inputs, previous_results, trace)
                _collect_artifacts(
                    result["result"],
                    trace,
                    tool_name=tool_name,
                    task_id=task.id,
                    goal_id=goal_id,
                    derived_from=derived_from,
                )
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


def _collect_artifacts(
    result: dict[str, Any],
    trace: ExecutionTrace,
    *,
    tool_name: str,
    task_id: str,
    goal_id: str,
    derived_from: list[str] | None = None,
) -> None:
    """Collect artifact IDs from a tool result, registering legacy path outputs."""
    _append_artifact_id(trace, result.get("artifact_id"))

    artifact = result.get("artifact")
    if isinstance(artifact, dict):
        _append_artifact_id(trace, artifact.get("id") or artifact.get("artifact_id"))

    for key in ("path", "audio_path", "image_path", "video_path"):
        _register_path_artifact(
            result.get(key),
            trace,
            produced_by=f"{tool_name}/{task_id}",
            goal_id=goal_id,
            derived_from=derived_from,
        )

    for item in result.get("artifacts", []):
        if isinstance(item, dict):
            if _append_artifact_id(trace, item.get("artifact_id") or item.get("id")):
                continue
            nested = item.get("artifact")
            if isinstance(nested, dict) and _append_artifact_id(
                trace,
                nested.get("id") or nested.get("artifact_id"),
            ):
                continue
            _register_path_artifact(
                item.get("path"),
                trace,
                produced_by=f"{tool_name}/{task_id}",
                goal_id=goal_id,
                derived_from=derived_from,
            )
        elif isinstance(item, str):
            _register_path_artifact(
                item,
                trace,
                produced_by=f"{tool_name}/{task_id}",
                goal_id=goal_id,
                derived_from=derived_from,
            )


def _append_artifact_id(trace: ExecutionTrace, artifact_id: Any) -> bool:
    if not artifact_id:
        return False
    artifact_id = str(artifact_id)
    if artifact_id not in trace.artifacts:
        trace.artifacts.append(artifact_id)
    return True


def _register_path_artifact(
    path: Any,
    trace: ExecutionTrace,
    *,
    produced_by: str,
    goal_id: str,
    derived_from: list[str] | None = None,
) -> None:
    if not path:
        return
    path = str(path)
    try:
        art = get_registry().add(Path(path), produced_by=produced_by, goal_id=goal_id, derived_from=derived_from)
    except RegistryError:
        # Preserve legacy behavior for path-only tools that report non-local paths.
        _append_artifact_id(trace, path)
    else:
        _append_artifact_id(trace, art.id)

def _resolve_lineage(
    inputs: dict[str, Any],
    previous_results: dict[str, Any],
    trace: ExecutionTrace,
) -> list[str]:
    """Resolve artifact IDs from input references to build derived_from lineage."""
    lineage: list[str] = []
    for ref_id, result in previous_results.items():
        if not isinstance(result, dict):
            continue
        # Check if this task's inputs reference the previous task's output
        input_str = json.dumps(inputs)
        ref_prefix = "${" + ref_id
        if ref_prefix in input_str:
            # Previous task produced artifacts that this task consumes
            for key in ("artifact_id", "path", "audio_path", "image_path", "video_path"):
                val = result.get(key)
                if val:
                    lineage.append(str(val))
                    break
            for item in result.get("artifacts", []):
                if isinstance(item, dict):
                    aid = item.get("artifact_id") or item.get("id")
                    if aid:
                        lineage.append(str(aid))
                elif isinstance(item, str):
                    lineage.append(item)
    # Resolve any raw paths to artifact IDs via the registry
    resolved: list[str] = []
    registry = get_registry()
    for val in lineage:
        # If it looks like an artifact ID (ULID: digits-dash-hex), use directly
        if len(val) == 28 and val[13] == "-" and not val.startswith("/"):
            resolved.append(val)
        else:
            # Try to resolve path to artifact ID via hash lookup
            try:
                p = Path(val)
                if p.exists():
                    from agent.artifact_registry import _sha256_of
                    h = _sha256_of(p)
                    matches = registry.find_by_hash(h)
                    if matches:
                        resolved.append(matches[0].id)
                    else:
                        resolved.append(val)  # keep path as fallback
                else:
                    resolved.append(val)
            except Exception:
                resolved.append(val)
    return list(dict.fromkeys(resolved))  # dedupe, preserve order

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
