"""Planner skeleton for become-manus-skill."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PlanTask:
    """Single task in a generated plan."""

    id: str
    goal: str
    tool: str | None = None
    inputs: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Plan:
    """Structured plan returned by the planner."""

    goal: str
    tasks: list[PlanTask]
    success_criteria: list[str] = field(default_factory=list)
    estimated_cost_usd: float = 0.0


def plan(goal: str, context: dict[str, Any] | None = None) -> Plan:
    """Create a plan for a goal."""
    raise NotImplementedError("Planner body is scaffolded for a later sprint phase.")
