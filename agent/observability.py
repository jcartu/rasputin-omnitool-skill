"""Real Langfuse-backed observability + cost telemetry.

Provides:
- @observe(name) decorator on planner/executor/reviewer/tool functions
- Cost tracking that pulls token counts from LLM responses
- CostCeilingExceeded raised when a goal exceeds its budget
- Trace IDs printed for each goal so user can open in Langfuse UI

If Langfuse is unreachable, the agent loop does not crash. It logs and proceeds.
"""
from __future__ import annotations

import logging
import os
import threading
import uuid
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ---- Langfuse client ----

_LF_CLIENT: Any = None
_LF_LOCK = threading.Lock()
_LF_ENABLED = False


def _get_langfuse():
    global _LF_CLIENT, _LF_ENABLED
    if _LF_CLIENT is not None:
        return _LF_CLIENT
    with _LF_LOCK:
        if _LF_CLIENT is not None:
            return _LF_CLIENT
        public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
        secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "")
        if not public_key or not secret_key:
            _LF_ENABLED = False
            return None
        try:
            from langfuse import Langfuse
            host = os.environ.get("LANGFUSE_HOST", "http://localhost:3000")
            # Langfuse 4.x uses base_url
            _LF_CLIENT = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                base_url=host,
            )
            _LF_ENABLED = True
        except Exception:
            _LF_ENABLED = False
            logger.warning("Failed to initialize Langfuse client", exc_info=True)
            return None
    return _LF_CLIENT


def is_langfuse_enabled() -> bool:
    """Return True if Langfuse is configured and reachable."""
    return _LF_ENABLED


# ---- Cost tracking ----


class CostCeilingExceeded(Exception):
    """Raised when cumulative goal cost would exceed MAX_COST_USD."""

    def __init__(self, current: float, limit: float, next_call_estimate: float):
        self.current = current
        self.limit = limit
        self.next_call_estimate = next_call_estimate
        super().__init__(
            f"cost ceiling: ${current:.4f} spent + ~${next_call_estimate:.4f} "
            f"next call > ${limit:.2f} ceiling"
        )


# Per-goal cost accumulator (thread-local)
_local = threading.local()


def _current_goal_cost() -> float:
    return getattr(_local, "cost_usd", 0.0)


def _add_cost(usd: float):
    _local.cost_usd = _current_goal_cost() + usd


def _reset_cost():
    _local.cost_usd = 0.0


# ---- Cost model ----
# Pricing as of May 2026 — update when models or pricing change.
# Format: (input_price_per_1M, output_price_per_1M)

PRICE_PER_M_TOKENS = {
    "claude-opus-4-7": (15.0, 75.0),
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-haiku-4-5": (0.80, 4.0),
    "qwen3-27b-instruct": (0.0, 0.0),
    "qwen3.5-27b-bf16": (0.0, 0.0),
    "qwen3.5-122b-a10b": (0.0, 0.0),
    "gpt-oss-120b": (0.0, 0.0),
}


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate USD cost for an LLM call given model and token counts."""
    in_price, out_price = PRICE_PER_M_TOKENS.get(model.lower(), (0.0, 0.0))
    return (prompt_tokens / 1_000_000) * in_price + (completion_tokens / 1_000_000) * out_price


def check_cost_ceiling(model: str, est_prompt: int, est_completion: int):
    """Call before an LLM call. Raises CostCeilingExceeded if it would push over the ceiling."""
    limit = float(os.environ.get("RASPUTIN_OMNITOOL_MAX_COST_USD", "0.50"))
    est_call = estimate_cost_usd(model, est_prompt, est_completion)
    current = _current_goal_cost()
    if current + est_call > limit:
        raise CostCeilingExceeded(current, limit, est_call)


def record_call_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Call after an LLM call. Adds the actual cost to the goal accumulator."""
    actual = estimate_cost_usd(model, prompt_tokens, completion_tokens)
    _add_cost(actual)
    return actual


# ---- Token usage extraction ----


def extract_usage(response: Any) -> tuple[int, int]:
    """Pull (prompt_tokens, completion_tokens) from any major SDK's response object."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return (0, 0)
    # Anthropic naming
    if hasattr(usage, "input_tokens"):
        return (getattr(usage, "input_tokens", 0), getattr(usage, "output_tokens", 0))
    # OpenAI / OpenCode Zen naming
    if hasattr(usage, "prompt_tokens"):
        return (getattr(usage, "prompt_tokens", 0), getattr(usage, "completion_tokens", 0))
    # Dict-shaped (some SDKs)
    if isinstance(usage, dict):
        prompt = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
        completion = usage.get("output_tokens") or usage.get("completion_tokens") or 0
        return (prompt, completion)
    return (0, 0)


def estimate_message_tokens(messages: list[dict[str, Any]]) -> int:
    """Approximate OpenAI-style chat token usage at ~4 characters per token."""
    total = 0
    for message in messages:
        content = message.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        total += max(1, len(content) // 4)
    return total


def truncate_observation(observation: dict[str, Any], max_chars: int) -> str:
    """Serialize and truncate a tool observation for model context."""
    import json

    text = json.dumps(observation, ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... [observation truncated; original length {len(text)} chars]"


# ---- @observe decorator ----


def observe(name: str | None = None):
    """Decorator: wraps a function in a Langfuse span.

    The decorated function may include `_span` in its signature; if present,
    the active span is passed in for adding events.
    """

    def decorator(func: Callable) -> Callable:
        span_name = name or func.__name__

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            lf = _get_langfuse()
            if lf is None:
                # No Langfuse — just run the function
                return func(*args, **kwargs)

            try:
                with lf.start_as_current_observation(
                    name=span_name, as_type="span"
                ) as obs:
                    # Pass observation to function if it accepts it
                    if "_span" in func.__code__.co_varnames:
                        kwargs["_span"] = obs
                    try:
                        result = func(*args, **kwargs)
                        if isinstance(result, dict) and "error" in result:
                            obs.update(level="ERROR", status_message=str(result["error"]))
                        return result
                    except Exception as exc:
                        obs.update(
                            level="ERROR",
                            status_message=f"{type(exc).__name__}: {exc}",
                        )
                        raise
            except Exception:
                # If Langfuse itself is unreachable, log and proceed
                logger.warning(
                    "langfuse_span_failed",
                    extra={"span": span_name},
                    exc_info=True,
                )
                if "_span" in func.__code__.co_varnames:
                    kwargs["_span"] = None
                return func(*args, **kwargs)

        return wrapper

    return decorator


# ---- Goal trace context manager ----


@contextmanager
def goal_trace(goal: str, goal_id: str | None = None):
    """Context manager wrapping an entire goal in a root trace.

    Resets the cost accumulator at entry. Prints the trace URL at exit.
    """
    lf = _get_langfuse()
    _reset_cost()
    goal_id = goal_id or f"goal-{uuid.uuid4().hex}"

    if lf is None:
        # No Langfuse — yield None, still track cost locally
        try:
            yield None
        finally:
            logger.info(
                f"goal {goal_id} completed. cost_usd={_current_goal_cost():.4f}"
            )
        return

    try:
        with lf.start_as_current_observation(
            name="run_goal",
            as_type="generation",
            input={"goal": goal, "goal_id": goal_id},
            metadata={"goal_id": goal_id},
        ) as obs:
            yield obs
            obs.update(
                metadata={
                    "goal_id": goal_id,
                    "total_cost_usd": _current_goal_cost(),
                }
            )
    finally:
        try:
            host = os.environ.get("LANGFUSE_HOST", "http://localhost:3000")
            trace_url = lf.get_trace_url() if hasattr(lf, "get_trace_url") else f"{host}/traces"
            logger.info(
                f"trace_url: {trace_url}  goal_id={goal_id}  "
                f"cost_usd={_current_goal_cost():.4f}"
            )
        except Exception:
            pass
        try:
            lf.flush()
        except Exception:
            pass


# ---- Backward compatibility ----


def set_goal_id(goal_id: str | None = None) -> str:
    """Set the current goal ID (backward compat with old observability API)."""
    if not goal_id:
        goal_id = f"goal-{uuid.uuid4().hex[:8]}"
    _local.goal_id = goal_id
    return goal_id
