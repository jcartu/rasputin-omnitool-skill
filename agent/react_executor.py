"""ReAct executor — model-in-the-loop agent with OpenAI tool calls."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable

from openai import OpenAI

from agent.config import CONFIG
from agent.executor import ExecutionTrace
from agent.observability import (
    CostCeilingExceeded,
    check_cost_ceiling,
    extract_usage,
    observe,
    record_call_cost,
)
from agent.planner import Plan
from agent.tool_registry import to_openai_tool_schemas

logger = logging.getLogger(__name__)


def _load_system_prompt() -> str:
    prompt_path = Path(__file__).resolve().parent.parent / "prompts" / "react_executor.md"
    return prompt_path.read_text(encoding="utf-8")


@observe("react_executor.execute")
def react_execute(
    goal: str,
    tools: dict[str, Callable[[dict], dict]],
    tool_metadata: list[dict],
    plan_hint: Plan | None = None,
    max_steps: int = 30,
    budget_usd: float = 0.50,
    max_wallclock_min: int = 20,
    soft_cap_tokens: int = 18_000,
    max_observation_chars: int = 8_000,
    goal_id: str | None = None,
) -> ExecutionTrace:
    """Run a ReAct agent loop until the goal is satisfied or a halt fires."""

    del goal_id
    started_at = time.time()
    trace = ExecutionTrace(plan=plan_hint or Plan(goal=goal, tasks=[]))
    trace.final_answer = None

    schemas = to_openai_tool_schemas(tool_metadata)
    if not schemas:
        trace.halted_for = "NO_TOOLS_AVAILABLE"
        return trace

    messages: list[dict] = [
        {"role": "system", "content": _load_system_prompt()},
        {"role": "user", "content": _format_user_message(goal, plan_hint, tool_metadata)},
    ]

    client = OpenAI(
        base_url=CONFIG.executor_endpoint,
        api_key=os.environ.get("OPENCODE_ZEN_API_KEY"),
    )
    model = CONFIG.executor_model
    recent_calls: list[tuple[str, str]] = []
    spent_usd = 0.0

    for step in range(max_steps):
        elapsed_min = (time.time() - started_at) / 60.0
        if elapsed_min > max_wallclock_min:
            trace.halted_for = "WALLCLOCK"
            break

        try:
            check_cost_ceiling(model, est_prompt=2000, est_completion=500)
        except CostCeilingExceeded:
            trace.halted_for = "BUDGET"
            break

        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=schemas,
                tool_choice="auto",
                temperature=0.2,
                max_tokens=1500,
            )
        except Exception as exc:
            trace.steps.append({
                "step": step,
                "kind": "model_error",
                "error": f"{type(exc).__name__}: {exc}",
            })
            trace.halted_for = "MODEL_ERROR"
            break

        prompt_tokens, completion_tokens = extract_usage(response)
        spent_usd += record_call_cost(model, prompt_tokens, completion_tokens)
        if spent_usd > budget_usd:
            trace.halted_for = "BUDGET"
            break

        choice = response.choices[0]
        msg = choice.message
        tool_calls = getattr(msg, "tool_calls", None) or []

        if choice.finish_reason == "stop" or not tool_calls:
            trace.final_answer = (msg.content or "").strip() or None
            trace.steps.append({
                "step": step,
                "kind": "final_answer",
                "content": trace.final_answer or "",
            })
            break

        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [_serialize_tool_call(tc) for tc in tool_calls],
        })

        any_useful_progress = False
        for tc in tool_calls:
            tool_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            args_hash = _hash_args(args)
            obs: dict[str, Any]

            if (tool_name, args_hash) in recent_calls[-5:]:
                obs = {
                    "error": {
                        "code": "DUPLICATE_TOOL_CALL",
                        "message": (
                            "You already called this tool with these arguments in the last 5 "
                            "steps. Pick a different approach."
                        ),
                    }
                }
            elif tool_name not in tools:
                obs = {
                    "error": {
                        "code": "UNKNOWN_TOOL",
                        "message": f"Tool '{tool_name}' is not available. Available: {sorted(tools.keys())}",
                    }
                }
            else:
                try:
                    obs = tools[tool_name](args)
                    if "result" in obs:
                        any_useful_progress = True
                        _collect_artifacts(obs["result"], trace)
                except Exception as exc:
                    obs = {
                        "error": {
                            "code": "TOOL_EXCEPTION",
                            "message": f"{type(exc).__name__}: {exc}",
                        }
                    }

            recent_calls.append((tool_name, args_hash))
            trace.steps.append({
                "step": step,
                "kind": "tool_call",
                "tool": tool_name,
                "args": args,
                "status": "ok" if "result" in obs else "error",
                "observation": obs,
                "observation_preview": _preview(obs, 400),
            })

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": _serialize_observation(obs, max_observation_chars),
            })

        if len(recent_calls) >= 5 and not any_useful_progress:
            last5 = recent_calls[-5:]
            if len(set(last5)) == 1:
                trace.halted_for = "DEDUP_LOOP"
                break

        messages = _compact_if_oversize(messages, soft_cap_tokens)
    else:
        trace.halted_for = "MAX_STEPS"

    return trace


def _format_user_message(goal: str, plan_hint: Plan | None, tool_metadata: list[dict]) -> str:
    payload = {
        "goal": goal,
        "available_tools": [
            {"name": t["name"], "description": t["description"], "tags": t.get("tags", [])}
            for t in tool_metadata
            if t["available"]
        ],
        "plan_hint": _plan_to_dict(plan_hint) if plan_hint else None,
    }
    return (
        "Solve the goal below. Use the available tools. Emit a final answer "
        "when the goal is satisfied — no tool call.\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def _plan_to_dict(plan: Plan) -> dict:
    return {
        "goal": plan.goal,
        "success_criteria": plan.success_criteria,
        "suggested_tasks": [
            {"id": task.id, "goal": task.goal, "tool": task.tool}
            for task in plan.tasks
        ],
    }


def _hash_args(args: dict) -> str:
    data = json.dumps(args, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


def _serialize_tool_call(tc: Any) -> dict:
    return {
        "id": tc.id,
        "type": "function",
        "function": {
            "name": tc.function.name,
            "arguments": tc.function.arguments,
        },
    }


def _serialize_observation(obs: dict, max_chars: int) -> str:
    text = json.dumps(obs, ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... [observation truncated; original length {len(text)} chars]"


def _preview(obs: dict, max_chars: int) -> str:
    text = json.dumps(obs, ensure_ascii=False, default=str)
    return text[:max_chars] + ("..." if len(text) > max_chars else "")


def _collect_artifacts(result: dict, trace: ExecutionTrace) -> None:
    artifact_id = result.get("artifact_id")
    if artifact_id:
        trace.artifacts.append(artifact_id)
        return
    for key in ("path", "audio_path", "image_path", "video_path"):
        value = result.get(key)
        if value:
            trace.artifacts.append(value)
    for artifact in result.get("artifacts", []):
        if isinstance(artifact, dict):
            if artifact.get("artifact_id"):
                trace.artifacts.append(artifact["artifact_id"])
            elif artifact.get("path"):
                trace.artifacts.append(artifact["path"])
        elif isinstance(artifact, str):
            trace.artifacts.append(artifact)


def _compact_if_oversize(messages: list[dict], soft_cap_tokens: int) -> list[dict]:
    estimated = sum(_estimate_tokens(message) for message in messages)
    if estimated <= soft_cap_tokens or len(messages) <= 8:
        return messages

    head = messages[:2]
    tail = messages[-6:]
    middle = messages[2:-6]
    pruned_middle: list[dict] = []
    drop_budget = max(1, len(middle) // 3)
    dropped = 0
    for message in middle:
        if dropped < drop_budget and message.get("role") in {"tool", "assistant"}:
            dropped += 1
            continue
        pruned_middle.append(message)

    compacted = head + pruned_middle + tail
    if sum(_estimate_tokens(message) for message in compacted) > soft_cap_tokens and len(compacted) > 8:
        return _compact_if_oversize(compacted, soft_cap_tokens)
    return compacted


def _estimate_tokens(message: dict) -> int:
    content = message.get("content", "")
    if isinstance(content, list):
        content = json.dumps(content)
    return max(1, len(str(content)) // 4)
