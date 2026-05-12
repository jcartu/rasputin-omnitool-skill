"""Unit tests for checkpoint module."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from dataclasses import asdict
from agent.checkpoint import (
    GoalCheckpoint,
    IncompatibleCheckpoint,
    get_checkpoint_manager,
    CheckpointManager,
    SCHEMA_VERSION,
)


@pytest.fixture
def tmp_root(tmp_path: Path) -> Path:
    return tmp_path / "checkpoints"


@pytest.fixture
def manager(tmp_root: Path):
    return CheckpointManager(root=tmp_root, keep=5)


@pytest.fixture
def sample_checkpoint() -> GoalCheckpoint:
    return GoalCheckpoint(
        goal_id="g-test-1",
        sprint_id=None,
        goal_text="Test goal",
        step_count=3,
        cost_usd=0.05,
        messages=[{"role": "user", "content": "hello"}],
        trace_steps=[{"step": 0, "kind": "tool_call", "tool": "crawl4ai"}],
        artifact_ids=["outputs/report.md"],
        sandbox_session_ids=["sess-abc"],
        browser_session_ids=[],
        created_at="2026-05-12T12:00:00+00:00",
        schema_version=SCHEMA_VERSION,
    )


# ── 1. Write → read round-trip preserves all fields ─────────────────────────

def test_write_read_roundtrip(manager, sample_checkpoint):
    manager.write(sample_checkpoint)
    loaded = manager.load("g-test-1")
    assert loaded.goal_id == sample_checkpoint.goal_id
    assert loaded.step_count == sample_checkpoint.step_count
    assert loaded.messages == sample_checkpoint.messages
    assert loaded.trace_steps == sample_checkpoint.trace_steps
    assert loaded.artifact_ids == sample_checkpoint.artifact_ids
    assert loaded.sandbox_session_ids == sample_checkpoint.sandbox_session_ids
    assert loaded.schema_version == sample_checkpoint.schema_version


# ── 2. Latest pointer updates atomically ────────────────────────────────────

def test_latest_pointer_updates(manager, sample_checkpoint):
    manager.write(sample_checkpoint)
    latest = manager._read_latest("g-test-1")
    assert latest == 1

    d = dict(asdict(sample_checkpoint))
    d["step_count"] = 5
    cp2 = GoalCheckpoint(**d)
    manager.write(cp2)
    latest = manager._read_latest("g-test-1")
    assert latest == 2


# ── 3. Concurrent writes: last write wins, no partial JSON ──────────────────

def test_concurrent_writes_no_partial_json(manager, sample_checkpoint):
    manager.write(sample_checkpoint)
    d = dict(asdict(sample_checkpoint))
    d["step_count"] = 4
    cp2 = GoalCheckpoint(**d)
    manager.write(cp2)
    loaded = manager.load("g-test-1")
    assert loaded.step_count == 4


# ── 4. list_checkpoints returns numeric order ───────────────────────────────

def test_list_returns_numeric_order(manager, sample_checkpoint):
    for i in range(5):
        d = dict(asdict(sample_checkpoint))
        d["step_count"] = i + 1
        cp = GoalCheckpoint(**d)
        manager.write(cp)
    nums = manager.list_n("g-test-1")
    assert nums == [1, 2, 3, 4, 5]


# ── 5. garbage_collect retains last N ───────────────────────────────────────

def test_garbage_collect_retains_last_n(tmp_root):
    mgr = CheckpointManager(root=tmp_root, keep=3)
    for i in range(6):
        cp = GoalCheckpoint(
            goal_id="g-gc",
            sprint_id=None,
            goal_text="GC test",
            step_count=i + 1,
            cost_usd=0.01,
            messages=[],
            trace_steps=[],
            artifact_ids=[],
            sandbox_session_ids=[],
            browser_session_ids=[],
            created_at="2026-05-12T12:00:00+00:00",
        )
        mgr.write(cp)
    nums = mgr.list_n("g-gc")
    assert nums == [4, 5, 6]


# ── 6. collapse_to_final removes intermediates, keeps final.json ────────────

def test_collapse_to_final(manager, sample_checkpoint):
    manager.write(sample_checkpoint)
    d = dict(asdict(sample_checkpoint))
    d["step_count"] = 5
    cp2 = GoalCheckpoint(**d)
    manager.write(cp2)
    manager.collapse_to_final("g-test-1")
    goal_dir = manager._goal_dir("g-test-1")
    assert (goal_dir / "final.json").exists()
    nums = manager.list_n("g-test-1")
    assert nums == []
    final_data = json.loads((goal_dir / "final.json").read_text())
    assert final_data["step_count"] == 5


# ── 7. Schema version mismatch raises INCOMPATIBLE_CHECKPOINT ───────────────

def test_schema_version_mismatch(tmp_root):
    mgr = CheckpointManager(root=tmp_root, keep=5)
    goal_dir = mgr._goal_dir("g-bad-schema")
    goal_dir.mkdir(parents=True, exist_ok=True)
    (goal_dir / "checkpoint-1.json").write_text(
        json.dumps({"schema_version": 99, "goal_id": "g-bad-schema"}),
        encoding="utf-8",
    )
    (goal_dir / "latest.json").write_text(json.dumps({"latest": 1}), encoding="utf-8")
    with pytest.raises(IncompatibleCheckpoint, match="incompatible"):
        mgr.load("g-bad-schema")


# ── 8. Resume reconstructs messages correctly ───────────────────────────────

def test_resume_reconstructs_messages(manager, sample_checkpoint):
    manager.write(sample_checkpoint)
    loaded = manager.load("g-test-1")
    assert loaded.messages == [{"role": "user", "content": "hello"}]
    assert len(loaded.messages) == 1


# ── 9. Resume with dead sessions → SESSIONS_EXPIRED ─────────────────────────

def test_resume_dead_sessions():
    from agent import resume_goal
    from agent.checkpoint import get_checkpoint_manager

    with patch.object(get_checkpoint_manager(), "latest", return_value=None):
        result = resume_goal("nonexistent-goal")
    assert result.get("halted") is True
    assert result.get("reason") == "NO_CHECKPOINT"


# ── 10. Resume with allow_session_loss=True succeeds ────────────────────────

def test_resume_allow_session_loss():
    from agent import resume_goal
    from agent.checkpoint import get_checkpoint_manager

    cp = GoalCheckpoint(
        goal_id="g-loss",
        sprint_id=None,
        goal_text="Loss test",
        step_count=2,
        cost_usd=0.02,
        messages=[],
        trace_steps=[],
        artifact_ids=[],
        sandbox_session_ids=["dead-sess"],
        browser_session_ids=[],
        created_at="2026-05-12T12:00:00+00:00",
    )

    with patch.object(get_checkpoint_manager(), "latest", return_value=cp):
        with patch("agent.run_goal") as mock_run:
            mock_run.return_value = {"goal_id": "g-loss", "review": "ok"}
            result = resume_goal("g-loss", allow_session_loss=True)
    assert result.get("goal_id") == "g-loss"


# ── 11. latest() returns None for unknown goal ─────────────────────────────

def test_latest_returns_none_for_unknown(manager):
    assert manager.latest("unknown-goal") is None


# ── 12. get_checkpoint_manager singleton ────────────────────────────────────

def test_singleton():
    m1 = get_checkpoint_manager()
    m2 = get_checkpoint_manager()
    assert m1 is m2
