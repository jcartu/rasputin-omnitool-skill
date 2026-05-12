"""Integration tests for checkpoint + resume."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.checkpoint import (
    CheckpointManager,
    GoalCheckpoint,
    get_checkpoint_manager,
)


@pytest.fixture
def tmp_root(tmp_path: Path) -> Path:
    return tmp_path / "checkpoints"


# ── 1. Kill-and-resume integration test ─────────────────────────────────────

def test_kill_and_resume(tmp_root, monkeypatch):
    """Simulate a goal that halts mid-flight, then resumes to completion."""
    monkeypatch.setenv("RASPUTIN_OMNITOOL_CHECKPOINT_ROOT", str(tmp_root))

    mgr = CheckpointManager(root=tmp_root, keep=5)

    # Phase 1: simulate partial execution (3 steps, then halt)
    cp = GoalCheckpoint(
        goal_id="g-integration-1",
        sprint_id=None,
        goal_text="Test integration goal",
        step_count=3,
        cost_usd=0.08,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Test integration goal"},
            {"role": "assistant", "content": "I'll search for the information.", "tool_calls": []},
            {"role": "tool", "content": "Search results: found 5 pages."},
            {"role": "assistant", "content": "Now I'll crawl the top result.", "tool_calls": []},
            {"role": "tool", "content": "Page content extracted."},
        ],
        trace_steps=[
            {"step": 0, "kind": "tool_call", "tool": "crawl4ai", "status": "ok"},
            {"step": 1, "kind": "tool_call", "tool": "crawl4ai", "status": "ok"},
            {"step": 2, "kind": "tool_call", "tool": "deliverables", "status": "ok"},
        ],
        artifact_ids=["outputs/draft.md"],
        sandbox_session_ids=[],
        browser_session_ids=[],
        created_at="2026-05-12T15:00:00+00:00",
    )
    mgr.write(cp)

    # Verify checkpoint was written
    loaded = mgr.load("g-integration-1")
    assert loaded.step_count == 3
    assert len(loaded.messages) == 6
    assert loaded.artifact_ids == ["outputs/draft.md"]

    # Phase 2: resume
    from agent import resume_goal

    with patch.object(get_checkpoint_manager(), "latest", return_value=loaded):
        with patch("agent.run_goal") as mock_run:
            mock_run.return_value = {
                "goal_id": "g-integration-1",
                "review": MagicMock(verdict="APPROVE"),
                "artifacts": ["outputs/report.md"],
            }
            result = resume_goal("g-integration-1", allow_session_loss=True)

    assert result["goal_id"] == "g-integration-1"
    assert result["review"].verdict == "APPROVE"


# ── 2. Resume with no checkpoint returns error ──────────────────────────────

def test_resume_no_checkpoint(tmp_root, monkeypatch):
    monkeypatch.setenv("RASPUTIN_OMNITOOL_CHECKPOINT_ROOT", str(tmp_root))

    from agent import resume_goal

    result = resume_goal("nonexistent-goal")
    assert result["halted"] is True
    assert result["reason"] == "NO_CHECKPOINT"


# ── 3. Checkpoint preserves messages for resume ─────────────────────────────

def test_checkpoint_preserves_messages_for_resume(tmp_root):
    mgr = CheckpointManager(root=tmp_root, keep=5)
    messages = [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "Write a report."},
        {"role": "assistant", "content": "I'll research this.", "tool_calls": []},
        {"role": "tool", "content": "Research complete."},
        {"role": "assistant", "content": "Now I'll write it.", "tool_calls": []},
    ]
    cp = GoalCheckpoint(
        goal_id="g-msg-test",
        sprint_id=None,
        goal_text="Write a report",
        step_count=2,
        cost_usd=0.03,
        messages=messages,
        trace_steps=[],
        artifact_ids=[],
        sandbox_session_ids=[],
        browser_session_ids=[],
        created_at="2026-05-12T15:00:00+00:00",
    )
    mgr.write(cp)
    loaded = mgr.load("g-msg-test")
    assert loaded.messages == messages
    assert len(loaded.messages) == 5


# ── 4. Multiple checkpoints increment N correctly ───────────────────────────

def test_multiple_checkpoints_increment_n(tmp_root):
    mgr = CheckpointManager(root=tmp_root, keep=10)
    for i in range(5):
        cp = GoalCheckpoint(
            goal_id="g-multi",
            sprint_id=None,
            goal_text="Multi-step goal",
            step_count=i + 1,
            cost_usd=0.01 * (i + 1),
            messages=[{"role": "user", "content": f"Step {i + 1}"}],
            trace_steps=[{"step": i, "kind": "tool_call", "tool": "crawl4ai"}],
            artifact_ids=[],
            sandbox_session_ids=[],
            browser_session_ids=[],
            created_at="2026-05-12T15:00:00+00:00",
        )
        mgr.write(cp)
    nums = mgr.list_n("g-multi")
    assert nums == [1, 2, 3, 4, 5]
    # Latest should be checkpoint 5
    latest = mgr.load("g-multi")
    assert latest.step_count == 5


# ── 5. Resume reconstructs trace steps ──────────────────────────────────────

def test_resume_reconstructs_trace_steps(tmp_root):
    mgr = CheckpointManager(root=tmp_root, keep=5)
    trace_steps = [
        {"step": 0, "kind": "tool_call", "tool": "crawl4ai", "status": "ok"},
        {"step": 1, "kind": "tool_call", "tool": "sandbox", "status": "ok"},
    ]
    cp = GoalCheckpoint(
        goal_id="g-trace",
        sprint_id=None,
        goal_text="Trace test",
        step_count=2,
        cost_usd=0.04,
        messages=[],
        trace_steps=trace_steps,
        artifact_ids=["outputs/result.txt"],
        sandbox_session_ids=["sess-abc"],
        browser_session_ids=[],
        created_at="2026-05-12T15:00:00+00:00",
    )
    mgr.write(cp)
    loaded = mgr.load("g-trace")
    assert loaded.trace_steps == trace_steps
    assert loaded.artifact_ids == ["outputs/result.txt"]
    assert loaded.sandbox_session_ids == ["sess-abc"]
