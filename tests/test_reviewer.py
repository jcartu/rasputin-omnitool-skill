from __future__ import annotations

from dataclasses import fields
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agent.executor import ExecutionTrace
from agent.planner import Plan, PlanTask
from agent.reviewer import ReviewParseError, review


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
        plan = Plan(
            goal="Produce the requested deliverable",
            tasks=[PlanTask(id="T1", goal="Create artifact", tool="deliverables")],
            success_criteria=["Artifact exists", "Validation passes"],
        )
        return ExecutionTrace(
            plan=plan,
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


def test_review_approve_on_clean_trace(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    create = _mock_anthropic(
        monkeypatch,
        '{"verdict":"APPROVE","notes":"Goal satisfied with coherent artifacts.","findings":[]}',
    )
    trace = _trace(
        steps=[{"step": "write", "status": "ok"}, {"step": "verify", "status": "ok"}],
        artifacts=["outputs/report.md"],
    )

    result = review(trace, ["outputs/report.md"])

    assert result.verdict == "APPROVE"
    assert result.findings == []
    assert "Goal satisfied" in result.notes
    assert create.call_args.kwargs["model"] == "claude-opus-4-7"
    assert create.call_args.kwargs["messages"][0]["role"] == "user"


def test_review_revise_with_findings(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    _mock_anthropic(
        monkeypatch,
        '{"verdict":"REVISE","notes":"One validation step is missing.","findings":["No artifact readability check was recorded."]}',
    )
    trace = _trace(steps=[{"step": "deliver", "status": "ok"}], artifacts=["outputs/data.csv"])

    result = review(trace, ["outputs/data.csv"])

    assert result.verdict == "REVISE"
    assert result.findings == ["No artifact readability check was recorded."]


def test_review_abort_on_severe_trace(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    _mock_anthropic(
        monkeypatch,
        '{"verdict":"ABORT","notes":"Trace contains unsupported success claims.","findings":["Claimed artifact path is absent.","Tool failure was hidden."]}',
    )
    trace = _trace(
        steps=[{"step": "fetch", "status": "error", "error": "browser timeout"}],
        halted_for="TOOL_FAILURE_RATE",
    )

    result = review(trace, [])

    assert result.verdict == "ABORT"
    assert "unsupported" in result.notes
    assert "Tool failure was hidden." in result.findings


def test_review_handles_malformed_opus_response(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    _mock_anthropic(monkeypatch, "not json")
    trace = _trace()

    with pytest.raises(ReviewParseError):
        review(trace, [])
