"""Skeleton for Phase 2: agent/react_executor.py — the model-in-the-loop agent.

This is the reference implementation Sisyphus must port to the project. Key
design decisions are pre-approved; do not redesign them in the phase work.

Design overview
---------------
The loop:
    messages = [system, user]
    while step < max_steps and cost < budget and wallclock < cap:
        response = model(messages, tools=tool_schemas)
        if response signals 'done' (stop reason or no tool call):
            break
        for each tool_call in response:
            args = parse_args(tool_call)
            if dedup(tool_call) or not_in_registry(tool_call):
                obs = synthesized_error
            else:
                obs = tools[name](args)
            append assistant turn + tool observation to messages
        compact_if_oversize(messages)

Termination signals:
    - finish_reason == 'stop'                       → final answer present
    - assistant message with no tool_calls          → final answer present
    - max_steps reached                             → halted_for = MAX_STEPS
    - cost > budget_usd                             → halted_for = BUDGET
    - wallclock > max_wallclock_min                 → halted_for = WALLCLOCK
    - dedup loop on every call in last 5 attempts   → halted_for = DEDUP_LOOP

Trace shape (unchanged from static executor — reviewer reads identically):
    ExecutionTrace.steps: list[dict]
    ExecutionTrace.artifacts: list[str]            # IDs (Phase 6) or paths
    ExecutionTrace.halted_for: str | None
    ExecutionTrace.final_answer: str | None        # NEW in Phase 2; reviewer ignores if absent
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from openai import OpenAI

# project imports — adjust to actual module paths
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


# --- system prompt loaded from prompts/react_executor.md at runtime ---

def _load_system_prompt() -> str:
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent / "prompts" / "react_executor.md"
    return p.read_text(encoding="utf-8")


# --- main entrypoint ---

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

    started_at = time.time()
    trace = ExecutionTrace(plan=plan_hint or Plan(goal=goal, tasks=[]))
    setattr(trace, "final_answer", None)

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
    model = getattr(CONFIG, "executor_model", "qwen3.5-27b-bf16")

    recent_calls: list[tuple[str, str]] = []   # (tool_name, args_hash) for dedup

    for step in range(max_steps):
        # --- pre-step halt checks ---
        elapsed_min = (time.time() - started_at) / 60.0
        if elapsed_min > max_wallclock_min:
            trace.halted_for = "WALLCLOCK"
            break

        try:
            check_cost_ceiling(model, est_prompt=2000, est_completion=500)
        except CostCeilingExceeded:
            trace.halted_for = "BUDGET"
            break

        # --- model call ---
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
        record_call_cost(model, prompt_tokens, completion_tokens)

        choice = response.choices[0]
        msg = choice.message

        # --- final-answer detection ---
        tool_calls = getattr(msg, "tool_calls", None) or []
        if choice.finish_reason == "stop" or not tool_calls:
            trace.final_answer = (msg.content or "").strip() or None
            trace.steps.append({
                "step": step,
                "kind": "final_answer",
                "content": trace.final_answer or "",
            })
            break

        # --- record assistant turn (with tool_calls) before the tool responses ---
        assistant_msg = {
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [_serialize_tool_call(tc) for tc in tool_calls],
        }
        messages.append(assistant_msg)

        # --- execute each tool call ---
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
                            "You already called this tool with these arguments "
                            "in the last 5 steps. Pick a different approach."
                        ),
                    }
                }
            elif tool_name not in tools:
                obs = {
                    "error": {
                        "code": "UNKNOWN_TOOL",
                        "message": (
                            f"Tool '{tool_name}' is not available. "
                            f"Available: {sorted(tools.keys())}"
                        ),
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
                "observation_preview": _preview(obs, 400),
            })

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": _serialize_observation(obs, max_observation_chars),
            })

        # --- dedup-loop halt: 5 in a row all dups or all errors with no progress ---
        if len(recent_calls) >= 5 and not any_useful_progress:
            last5 = recent_calls[-5:]
            if len(set(last5)) == 1:
                trace.halted_for = "DEDUP_LOOP"
                break

        # --- context compaction ---
        messages = _compact_if_oversize(messages, soft_cap_tokens)
    else:
        trace.halted_for = "MAX_STEPS"

    return trace


# --- helpers ---

def _format_user_message(goal: str, plan_hint: Plan | None, tool_metadata: list[dict]) -> str:
    payload = {
        "goal": goal,
        "available_tools": [
            {"name": t["name"], "description": t["description"], "tags": t.get("tags", [])}
            for t in tool_metadata if t["available"]
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
            {"id": t.id, "goal": t.goal, "tool": t.tool}
            for t in plan.tasks
        ],
    }


def _hash_args(args: dict) -> str:
    s = json.dumps(args, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


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
    truncated = text[:max_chars]
    return (
        truncated
        + f"\n... [observation truncated; original length {len(text)} chars]"
    )


def _preview(obs: dict, max_chars: int) -> str:
    text = json.dumps(obs, ensure_ascii=False, default=str)
    return text[:max_chars] + ("..." if len(text) > max_chars else "")


def _collect_artifacts(result: dict, trace: ExecutionTrace) -> None:
    """Pull artifact IDs (or paths, pre-Phase-6) into the trace."""
    # Phase 6 wraps these into typed artifacts; for Phase 2 we just append paths.
    aid = result.get("artifact_id")
    if aid:
        trace.artifacts.append(aid)
        return
    for key in ("path", "audio_path", "image_path", "video_path"):
        v = result.get(key)
        if v:
            trace.artifacts.append(v)
    for a in result.get("artifacts", []):
        if isinstance(a, dict):
            if a.get("artifact_id"):
                trace.artifacts.append(a["artifact_id"])
            elif a.get("path"):
                trace.artifacts.append(a["path"])
        elif isinstance(a, str):
            trace.artifacts.append(a)


def _compact_if_oversize(messages: list[dict], soft_cap_tokens: int) -> list[dict]:
    """Drop oldest tool observations when over the soft cap.

    Preserves: system message, original user message, and the last 4 turns.
    Drops middle tool observations first, oldest first.
    """
    estimated = sum(_estimate_tokens(m) for m in messages)
    if estimated <= soft_cap_tokens:
        return messages

    if len(messages) <= 8:
        return messages

    head = messages[:2]                # system + original user
    tail = messages[-6:]               # last few turns (asst + tool pairs)
    middle = messages[2:-6]

    # Drop oldest 'tool' messages first, then oldest 'assistant' messages with tool_calls.
    pruned_middle: list[dict] = []
    drop_budget = max(1, len(middle) // 3)
    dropped = 0
    for m in middle:
        if dropped < drop_budget and m.get("role") in ("tool", "assistant"):
            dropped += 1
            continue
        pruned_middle.append(m)

    compacted = head + pruned_middle + tail
    new_estimate = sum(_estimate_tokens(m) for m in compacted)
    if new_estimate > soft_cap_tokens and len(compacted) > 8:
        # one more pass
        return _compact_if_oversize(compacted, soft_cap_tokens)
    return compacted


def _estimate_tokens(msg: dict) -> int:
    """Very rough — ~4 chars per token."""
    content = msg.get("content", "")
    if isinstance(content, list):
        content = json.dumps(content)
    return max(1, len(str(content)) // 4)
