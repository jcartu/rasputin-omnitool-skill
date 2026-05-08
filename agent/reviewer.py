"""Reviewer skeleton for become-manus-skill."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent.executor import ExecutionTrace


@dataclass(frozen=True)
class Review:
    """Review result for a completed or checkpointed execution."""

    passed: bool
    findings: list[str] = field(default_factory=list)
    required_fixes: list[str] = field(default_factory=list)
    score: float | None = None


def review(trace: ExecutionTrace, context: dict[str, Any] | None = None) -> Review:
    """Review an execution trace."""
    raise NotImplementedError("Reviewer body is scaffolded for a later sprint phase.")
