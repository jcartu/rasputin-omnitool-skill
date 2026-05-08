"""Observability decorators. Writes structured trace events to runlog (PHASE-5 swaps to Langfuse)."""
from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar, cast

F = TypeVar("F", bound=Callable[..., Any])

_current_goal_id: ContextVar[str] = ContextVar("current_goal_id", default="")


def set_goal_id(goal_id: str | None = None) -> str:
    """Set the current goal ID for trace grouping. Returns the goal ID."""
    if not goal_id:
        goal_id = f"goal-{uuid.uuid4().hex[:8]}"
    _current_goal_id.set(goal_id)
    return goal_id


def _emit_span(
    goal_id: str,
    span_id: str,
    span_name: str,
    started: float,
    ended: float,
    status: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    result: Any,
) -> None:
    """Write a structured span event to runlog/traces/."""
    trace_dir = Path("runlog/traces") / goal_id
    trace_dir.mkdir(parents=True, exist_ok=True)

    # Serialize args/kwargs/result safely (truncate large payloads)
    def _safe_serialize(obj: Any, max_len: int = 40000) -> Any:
        try:
            s = json.dumps(obj, default=str)
            if len(s) > max_len:
                return s[:max_len] + "... [truncated]"
            return s
        except Exception:
            return str(obj)[:max_len]

    span_data = {
        "goal_id": goal_id,
        "span_id": span_id,
        "name": span_name,
        "started_at": started,
        "ended_at": ended,
        "duration_s": round(ended - started, 4),
        "status": status,
        "args": _safe_serialize(list(args)),
        "kwargs": _safe_serialize(kwargs),
        "result": _safe_serialize(result) if status == "ok" else None,
    }

    path = trace_dir / f"{span_id}.json"
    path.write_text(json.dumps(span_data, indent=2) + "\n")


def observe(name: str | None = None) -> Callable[[F], F]:
    """Decorator that traces a function call to runlog/traces/.

    Until PHASE-5 wires Langfuse, this writes structured JSON span events
    to runlog/traces/<goal-id>/<span-id>.json.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            goal_id = _current_goal_id.get()
            if not goal_id:
                goal_id = f"goal-{uuid.uuid4().hex[:8]}"
                _current_goal_id.set(goal_id)

            span_id = uuid.uuid4().hex[:12]
            span_name = name or func.__name__
            started = time.time()

            try:
                result = func(*args, **kwargs)
                _emit_span(goal_id, span_id, span_name, started, time.time(), "ok", args, kwargs, result)
                return result
            except Exception as exc:
                _emit_span(goal_id, span_id, span_name, started, time.time(), "error", args, kwargs, str(exc))
                raise

        return cast(F, wrapper)

    return decorator
