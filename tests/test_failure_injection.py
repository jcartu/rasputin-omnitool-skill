"""Failure injection tests for the agent loop."""
from __future__ import annotations

import json
from dataclasses import fields
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from agent.executor import execute, ExecutionTrace
from agent.planner import Plan, PlanTask, PlannerOutputError, plan
from agent.reviewer import review


# ── Helpers ──────────────────────────────────────────────────────────────


def _mock_anthropic(monkeypatch: pytest.MonkeyPatch, text: str) -> Mock:
    create = Mock(return_value=SimpleNamespace(content=[SimpleNamespace(text=text)]))
    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    anthropic_cls = Mock(return_value=client)
    monkeypatch.setattr("agent.reviewer.anthropic.Anthropic", anthropic_cls)
    return create


def _trace(
    *,
    steps: list[dict[str, object]] | None = None,
    artifacts: list[str] | None = None,
    halted_for: str | None = None,
) -> ExecutionTrace:
    trace_fields = {field.name for field in fields(ExecutionTrace)}
    resolved_steps = steps or [{"task_id": "T1", "tool": "deliverables", "status": "ok"}]
    if "plan" in trace_fields:
        plan_obj = Plan(
            goal="Test goal",
            tasks=[PlanTask(id="T1", goal="Create artifact", tool="deliverables")],
            success_criteria=["Artifact exists"],
        )
        return ExecutionTrace(
            plan=plan_obj,
            steps=resolved_steps,
            artifacts=artifacts or [],
            halted_for=halted_for,
        )
    return ExecutionTrace(
        plan_id="plan-1",
        events=resolved_steps,
        artifacts=artifacts or [],
        errors=[] if halted_for is None else [{"halted_for": halted_for}],
    )


# ── 4.9.1 — Tool failure propagates to reviewer ─────────────────────────


def test_tool_failure_propagates_to_review(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """A tool returns an error mid-execute; the reviewer sees it in the trace."""
    monkeypatch.chdir(tmp_path)

    _mock_anthropic(
        monkeypatch,
        json.dumps({
            "verdict": "REVISE",
            "notes": "Tool failure detected in step T2.",
            "findings": ["crawl4ai returned HTTP 500 on task-2"],
        }),
    )

    trace = _trace(
        steps=[
            {"task_id": "T1", "tool": "crawl4ai", "status": "ok", "output": {"result": {"markdown": "Example Domain"}}},
            {"task_id": "T2", "tool": "crawl4ai", "status": "error", "error": "HTTP 500: Internal Server Error"},
        ],
        artifacts=["outputs/summary.md"],
    )

    result = review(trace, ["outputs/summary.md"])

    assert result.verdict == "REVISE"
    assert len(result.findings) >= 1
    assert "failure" in result.notes.lower() or "error" in result.notes.lower() or "500" in result.findings[0]


# ── 4.9.2 — Planner invalid tool caught at validation ───────────────────


class FakeCompletions:
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = self.responses.pop(0)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


class FakeClient:
    def __init__(self, responses: list[str]):
        self.completions = FakeCompletions(responses)
        self.chat = SimpleNamespace(completions=self.completions)


def test_planner_invalid_tool_caught_at_validation() -> None:
    """Mock planner to emit a tool name not in catalog; assert PlannerOutputError."""
    bad_plan = json.dumps({
        "goal": "Test goal",
        "tasks": [
            {
                "id": "task-1",
                "goal": "Do something with a made-up tool",
                "tool": "nonexistent_tool",
                "inputs": {},
                "depends_on": [],
            }
        ],
        "success_criteria": ["Done"],
        "estimated_cost_usd": 0.0,
    })

    # Planner retries on validation failure — need 2 bad responses to exhaust retries.
    client = FakeClient([bad_plan, bad_plan])
    with patch("agent.planner.OpenAI", return_value=client):
        with pytest.raises(PlannerOutputError):
            plan(
                "Test goal",
                tools=[{"name": "catalog", "capabilities": ["discover_tools"]}],
            )

    # Two attempts (initial + retry).
    assert len(client.completions.calls) == 2


# ── 4.9.3 — Executor malformed tool call recovers ────────────────────────


def test_executor_malformed_tool_call_recovers() -> None:
    """Executor marks a task as failure when the tool is missing, then continues until halt threshold."""
    plan_obj = Plan(
        goal="Test goal",
        tasks=[
            PlanTask(id="T1", goal="Task 1", tool="good_tool", inputs={}),
            PlanTask(id="T2", goal="Task 2", tool="bad_tool", inputs={}),
            PlanTask(id="T3", goal="Task 3", tool="good_tool", inputs={}),
        ],
    )

    call_count = [0]

    def good_tool(inp):
        call_count[0] += 1
        return {"result": {"output": f"step-{call_count[0]}"}}

    tools = {
        "good_tool": good_tool,
        # "bad_tool" is intentionally absent from registry.
    }

    trace = execute(plan_obj, tools)

    # T1 succeeds, T2 is error. After T2: 1/2 = 50% failure rate > 30% threshold.
    # So executor halts at TOOL_FAILURE_RATE before reaching T3.
    assert len(trace.steps) == 2
    assert trace.steps[0]["status"] == "ok"
    assert trace.steps[1]["status"] == "error"
    assert "not found" in trace.steps[1]["error"]
    # Halted due to failure rate.
    assert trace.halted_for == "TOOL_FAILURE_RATE"


# ── 4.9.4 — Review findings drive replan ─────────────────────────────────


def test_review_findings_drive_replan(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """First review is REVISE with specific finding; second plan addresses it."""
    monkeypatch.chdir(tmp_path)

    # First review: REVISE with a finding about missing citations.
    first_verdict = json.dumps({
        "verdict": "REVISE",
        "notes": "Missing citations in the deliverable.",
        "findings": ["No source URLs included in the markdown output."],
    })

    # Second review: APPROVE after replan.
    second_verdict = json.dumps({
        "verdict": "APPROVE",
        "notes": "Citations now included.",
        "findings": [],
    })

    anthropic_calls = [first_verdict, second_verdict]

    def mock_create(**kwargs):
        text = anthropic_calls.pop(0)
        return SimpleNamespace(content=[SimpleNamespace(text=text)])

    mock_client = SimpleNamespace(messages=SimpleNamespace(create=Mock(side_effect=mock_create)))
    mock_anthropic_cls = Mock(return_value=mock_client)
    monkeypatch.setattr("agent.reviewer.anthropic.Anthropic", mock_anthropic_cls)

    # Build first trace — missing citations.
    trace1 = _trace(
        steps=[{"task_id": "T1", "tool": "deliverables", "status": "ok", "output": {"result": {"path": "outputs/report.md"}}}],
        artifacts=["outputs/report.md"],
    )

    rev1 = review(trace1, ["outputs/report.md"])
    assert rev1.verdict == "REVISE"
    assert "citations" in rev1.notes.lower() or "source" in rev1.findings[0].lower()

    # Build second trace — citations included.
    trace2 = _trace(
        steps=[
            {"task_id": "T1", "tool": "deliverables", "status": "ok", "output": {"result": {"path": "outputs/report.md"}}},
            {"task_id": "T2", "tool": "deliverables", "status": "ok", "output": {"result": {"path": "outputs/citations.md"}}},
        ],
        artifacts=["outputs/report.md", "outputs/citations.md"],
    )

    rev2 = review(trace2, ["outputs/report.md", "outputs/citations.md"])
    assert rev2.verdict == "APPROVE"
