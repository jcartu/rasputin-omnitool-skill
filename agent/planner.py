"""Planner implementation for rasputin-omnitool-skill."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from agent.config import CONFIG
from agent.observability import observe


PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "planner.md"


class PlannerOutputError(ValueError):
    """Raised when the planner model cannot produce a valid plan."""


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


class PlanTaskModel(BaseModel):
    """Pydantic schema for one planned task."""

    id: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    tool: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)


class PlanModel(BaseModel):
    """Pydantic schema for planner output."""

    goal: str = Field(min_length=1)
    tasks: list[PlanTaskModel] = Field(min_length=1)
    success_criteria: list[str] = Field(default_factory=list)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)

    def to_plan(self) -> Plan:
        """Convert the validated model into the public dataclass API."""

        return Plan(
            goal=self.goal,
            tasks=[
                PlanTask(
                    id=task.id,
                    goal=task.goal,
                    tool=task.tool,
                    inputs=dict(task.inputs),
                    depends_on=list(task.depends_on),
                )
                for task in self.tasks
            ],
            success_criteria=list(self.success_criteria),
            estimated_cost_usd=self.estimated_cost_usd,
        )


def _load_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _tool_names(tools: list[dict]) -> set[str]:
    names: set[str] = set()
    for tool in tools:
        name = tool.get("name")
        if isinstance(name, str) and name:
            names.add(name)
    return names


def _build_messages(goal: str, tools: list[dict], context: dict[str, Any] | None) -> list[dict[str, str]]:
    payload = {
        "goal": goal,
        "tool_catalog": tools,
        "context": context or {},
        "output_contract": "Return only a JSON object matching the planner schema.",
    }
    return [
        {"role": "system", "content": _load_system_prompt()},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
    ]


def _extract_content(response: Any) -> str:
    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError, TypeError) as exc:
        raise PlannerOutputError("Planner response did not contain message content.") from exc
    if not isinstance(content, str) or not content.strip():
        raise PlannerOutputError("Planner response content was empty.")
    return content


def _validate_plan(content: str, allowed_tools: set[str]) -> PlanModel:
    try:
        if hasattr(PlanModel, "model_validate_json"):
            model = PlanModel.model_validate_json(content)
        else:
            model = PlanModel.parse_raw(content)
    except (ValidationError, ValueError) as exc:
        raise PlannerOutputError("Planner returned malformed plan JSON.") from exc

    unknown_tools = sorted({task.tool for task in model.tasks if task.tool and task.tool not in allowed_tools})
    if unknown_tools:
        raise PlannerOutputError(f"Planner used tools outside the catalog: {', '.join(unknown_tools)}")
    return model


def _completion(client: OpenAI, messages: list[dict[str, str]], retry_error: str | None = None) -> str:
    request_messages = list(messages)
    if retry_error:
        request_messages.append(
            {
                "role": "user",
                "content": (
                    "The previous response failed validation: "
                    f"{retry_error}. Return a corrected JSON object only."
                ),
            }
        )

    response = client.chat.completions.create(
        model=CONFIG.planner_model,
        messages=request_messages,
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    return _extract_content(response)


@observe("planner.plan")
def plan(goal: str, tools: list[dict], context: dict[str, Any] | None = None) -> Plan:
    """Create a validated plan for a goal using the configured planner model."""

    allowed_tools = _tool_names(tools)
    messages = _build_messages(goal, tools, context)
    client = OpenAI(
        base_url=CONFIG.executor_endpoint,
        api_key=os.environ.get("OPENCODE_ZEN_API_KEY"),
    )

    last_error: PlannerOutputError | None = None
    for attempt in range(2):
        content = _completion(client, messages, str(last_error) if last_error else None)
        try:
            return _validate_plan(content, allowed_tools).to_plan()
        except PlannerOutputError as exc:
            last_error = exc
            if attempt == 1:
                raise PlannerOutputError("Planner failed to produce a valid plan after retry.") from exc

    raise PlannerOutputError("Planner failed to produce a valid plan.")
