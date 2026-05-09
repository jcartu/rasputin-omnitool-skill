from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from agent.planner import Plan, PlannerOutputError, plan


class FakeCompletions:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = self.responses.pop(0)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


class FakeClient:
    def __init__(self, responses: list[str]) -> None:
        self.completions = FakeCompletions(responses)
        self.chat = SimpleNamespace(completions=self.completions)


def valid_plan(tool: str = "web_search") -> str:
    return json.dumps(
        {
            "goal": "Research durable browser automation options.",
            "tasks": [
                {
                    "id": "task-1",
                    "goal": "Collect cited sources about durable browser automation options.",
                    "tool": tool,
                    "inputs": {"require_citations": True},
                    "depends_on": [],
                }
            ],
            "success_criteria": ["Research includes cited recommendations."],
            "estimated_cost_usd": 0.01,
        }
    )


def run_with_responses(responses: list[str], tools: list[dict] | None = None) -> tuple[Plan, FakeClient]:
    client = FakeClient(responses)
    with patch("agent.planner.OpenAI", return_value=client):
        result = plan(
            "Research durable browser automation options.",
            tools or [{"name": "web_search", "capabilities": ["research"]}],
        )
    return result, client


def test_planner_returns_valid_plan_for_research_goal() -> None:
    result, client = run_with_responses([valid_plan()])

    assert result.goal == "Research durable browser automation options."
    assert result.tasks[0].id == "task-1"
    assert result.tasks[0].tool == "web_search"
    assert result.success_criteria == ["Research includes cited recommendations."]
    request = client.completions.calls[0]
    assert request["temperature"] == 0.2
    assert request["response_format"] == {"type": "json_object"}


def test_planner_handles_malformed_response_with_retry() -> None:
    result, client = run_with_responses(["not-json", valid_plan()])

    assert result.tasks[0].tool == "web_search"
    assert len(client.completions.calls) == 2
    retry_messages = client.completions.calls[1]["messages"]
    assert "previous response failed validation" in retry_messages[-1]["content"]


def test_planner_raises_on_persistent_malformation() -> None:
    client = FakeClient(["not-json", json.dumps({"goal": "missing tasks"})])

    with patch("agent.planner.OpenAI", return_value=client):
        with pytest.raises(PlannerOutputError):
            plan(
                "Research durable browser automation options.",
                [{"name": "web_search", "capabilities": ["research"]}],
            )

    assert len(client.completions.calls) == 2


def test_planner_only_uses_tools_in_catalog() -> None:
    result, client = run_with_responses(
        [valid_plan("made_up_tool"), valid_plan("catalog")],
        tools=[{"name": "catalog", "capabilities": ["discover_tools"]}],
    )

    assert result.tasks[0].tool == "catalog"
    assert len(client.completions.calls) == 2
