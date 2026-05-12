"""Integration tests for the full agent loop."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from agent import run_goal
from agent.executor import ExecutionTrace


# ── 4-7 — Full loop with mocked tools ────────────────────────────────────


def test_run_goal_with_mocked_tools(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Full plan → execute → review loop completes with mocked tools in ≤2 minutes."""
    monkeypatch.chdir(tmp_path)

    # Mock planner to return a deterministic 2-task plan.
    plan_json = json.dumps({
        "goal": "Produce a markdown report from a crawl.",
        "tasks": [
            {
                "id": "task-1",
                "goal": "Crawl example.com and extract markdown.",
                "tool": "crawl4ai",
                "inputs": {"url": "http://example.com"},
                "depends_on": [],
            },
            {
                "id": "task-2",
                "goal": "Write a 1-paragraph markdown summary to outputs/.",
                "tool": "deliverables",
                "inputs": {"format": "markdown", "title": "Example.com Summary"},
                "depends_on": ["task-1"],
            },
        ],
        "success_criteria": ["Markdown file exists in outputs/"],
        "estimated_cost_usd": 0.0,
    })

    fake_plan_completions = Mock()
    fake_plan_completions.create = Mock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=plan_json))]
        )
    )
    fake_plan_chat = SimpleNamespace(completions=fake_plan_completions)
    fake_plan_client = SimpleNamespace(chat=fake_plan_chat)

    def fake_openai(**kwargs):
        return fake_plan_client

    monkeypatch.setattr("agent.planner.OpenAI", fake_openai)

    # Mock reviewer to return APPROVE.
    review_json = json.dumps({
        "verdict": "APPROVE",
        "notes": "Goal satisfied with coherent artifacts.",
        "findings": [],
    })
    fake_review_create = Mock(
        return_value=SimpleNamespace(content=[SimpleNamespace(text=review_json)])
    )
    fake_review_client = SimpleNamespace(
        messages=SimpleNamespace(create=fake_review_create)
    )
    fake_anthropic_cls = Mock(return_value=fake_review_client)
    monkeypatch.setattr("agent.reviewer.anthropic.Anthropic", fake_anthropic_cls)

    # Mock tool metadata loader (patch at the import site used by agent/__init__.py).
    monkeypatch.setattr(
        "agent.load_tool_metadata",
        lambda: [
            {"name": "crawl4ai", "description": "Web crawler"},
            {"name": "deliverables", "description": "File generator"},
        ],
    )

    # Mock tool registry (patch at the import site used by agent/__init__.py).
    def mock_load_tools():
        return {
            "crawl4ai": lambda inp: {
                "result": {"markdown": "Example Domain\n\nThis domain is for use in documentation.", "url": "http://example.com"}
            },
            "deliverables": lambda inp: {
                "result": {"path": "outputs/summary.md", "artifacts": [{"path": "outputs/summary.md", "name": "summary.md"}]}
            },
        }

    monkeypatch.setattr("agent.load_tools", mock_load_tools)

    start = time.time()
    result = run_goal("Crawl example.com and produce a 1-paragraph markdown summary saved to outputs/.")
    elapsed = time.time() - start

    # Assertions
    assert result["plan"] is not None
    assert isinstance(result["trace"], ExecutionTrace)
    assert len(result["trace"].steps) == 2
    assert result["review"].verdict == "APPROVE"
    assert result["revised"] is False
    # Completed within 2 minutes.
    assert elapsed < 120, f"Loop took {elapsed:.1f}s, expected <120s"

    # Write trace for inspection.
    runlog_dir = Path("runlog/test-traces")
    runlog_dir.mkdir(parents=True, exist_ok=True)
    (runlog_dir / "test_mocked_loop.json").write_text(
        json.dumps({"elapsed_s": round(elapsed, 2), "steps": len(result["trace"].steps), "verdict": result["review"].verdict}, indent=2)
    )


# ── 4-8 — Full loop with REAL tools ──────────────────────────────────────


@pytest.mark.skip(reason="Integration test requiring specific model setup")
@pytest.mark.skipif(
    not os.environ.get("OPENCODE_ZEN_API_KEY"),
    reason="Requires OPENCODE_ZEN_API_KEY for real planner calls",
)
def test_run_goal_research_simple() -> None:
    """Full loop with real crawl4ai + deliverables tools completes in ≤5 minutes."""
    start = time.time()
    result = run_goal("Crawl http://example.com and produce a 1-paragraph markdown summary saved to outputs/.")
    elapsed = time.time() - start

    # Assertions
    assert result["plan"] is not None
    assert isinstance(result["trace"], ExecutionTrace)
    assert len(result["trace"].steps) >= 1
    # Completed within 5 minutes.
    assert elapsed < 300, f"Loop took {elapsed:.1f}s, expected <300s"

    # At least one artifact produced.
    assert len(result["artifacts"]) >= 1

    # Write trace for inspection.
    runlog_dir = Path("runlog/test-traces")
    runlog_dir.mkdir(parents=True, exist_ok=True)
    (runlog_dir / "test_real_tools_loop.json").write_text(
        json.dumps({"elapsed_s": round(elapsed, 2), "steps": len(result["trace"].steps), "artifacts": result["artifacts"], "verdict": result["review"].verdict}, indent=2)
    )
