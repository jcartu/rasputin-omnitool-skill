"""Observability hooks for become-manus-skill."""
from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, cast


F = TypeVar("F", bound=Callable[..., Any])


def observe(name: str | None = None) -> Callable[[F], F]:
    """Pass-through decorator until Langfuse wiring lands in PHASE-5."""

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        return cast(F, wrapper)

    return decorator
