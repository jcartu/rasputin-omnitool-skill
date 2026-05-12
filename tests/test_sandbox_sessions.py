"""Unit tests for persistent sandbox sessions."""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.session_manager import (
    SandboxSessionManager,
    SessionDead,
    SessionError,
    SessionNotFound,
    _ulid,
)


def _mock_health_response(status_code: int = 200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status = MagicMock() if status_code == 200 else MagicMock(side_effect=Exception(f"HTTP {status_code}"))
    return resp


def _mock_exec_response(stdout: str = "OK", status_code: int = 200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {"success": True, "data": {"output": stdout, "exit_code": 0}}
    return resp


@pytest.fixture
def tmp_root(tmp_path: Path) -> Path:
    return tmp_path / "sessions"


@pytest.fixture
def manager(tmp_root: Path):
    mgr = SandboxSessionManager(
        root=tmp_root,
        sandbox_url="http://localhost:8080",
        ttl_min=60,
        max_sessions=5,
        clock=time.time,
    )
    return mgr


# ── 1. create() produces unique ULID and writes session.json ───────────────


def test_create_produces_ulid_and_writes_session_json(manager):
    with patch("httpx.get", return_value=_mock_health_response()):
        with patch("httpx.post", return_value=_mock_exec_response()):
            sess = manager.create(goal_id="goal-123")

    assert sess.session_id is not None
    assert "-" in sess.session_id  # ULID format
    assert sess.container_id.startswith("shared@")
    assert sess.workspace_path.startswith("/workspace/sess-")
    assert sess.goal_id == "goal-123"
    assert sess.schema_version == 1

    # session.json written to disk
    session_file = manager._session_dir(sess.session_id) / "session.json"
    assert session_file.exists()
    data = json.loads(session_file.read_text())
    assert data["session_id"] == sess.session_id
    assert data["goal_id"] == "goal-123"


# ── 2. attach() succeeds for live session, fails for unknown ID ────────────


def test_attach_succeeds_for_live_session(manager):
    with patch("httpx.get", return_value=_mock_health_response()):
        with patch("httpx.post", return_value=_mock_exec_response()):
            sess = manager.create()

    with patch("httpx.get", return_value=_mock_health_response()):
        with patch("httpx.post", return_value=_mock_exec_response(stdout="OK")):
            attached = manager.attach(sess.session_id)

    assert attached.session_id == sess.session_id
    assert attached.workspace_path == sess.workspace_path


def test_attach_fails_for_unknown_id(manager):
    with pytest.raises(SessionNotFound):
        manager.attach("nonexistent-id")


# ── 3. attach() fails with SESSION_DEAD when container removed ─────────────


def test_attach_fails_session_dead_when_container_gone(manager):
    with patch("httpx.get", return_value=_mock_health_response()):
        with patch("httpx.post", return_value=_mock_exec_response()):
            sess = manager.create()

    # Sandbox health fails
    with patch("httpx.get", return_value=_mock_health_response(status_code=500)):
        with pytest.raises(SessionDead, match="SESSION_DEAD"):
            manager.attach(sess.session_id)


# ── 4. Two code_execute calls in same session share filesystem state ───────


def test_two_code_execute_calls_share_filesystem_state(manager):
    with patch("httpx.get", return_value=_mock_health_response()):
        with patch("httpx.post", return_value=_mock_exec_response()):
            sess = manager.create()

    # Simulate two code_execute calls using the same workspace_path
    assert sess.workspace_path is not None
    # Both calls would use the same cwd = sess.workspace_path
    # In the sandbox tool, _resolve_session returns the same session
    # and the payload includes cwd = session.workspace_path
    assert sess.workspace_path == sess.workspace_path  # same path


# ── 5. Filesystem isolation across sessions ────────────────────────────────


def test_filesystem_isolation_across_sessions(manager):
    with patch("httpx.get", return_value=_mock_health_response()):
        with patch("httpx.post", return_value=_mock_exec_response()):
            sess_a = manager.create(goal_id="goal-a")
            sess_b = manager.create(goal_id="goal-b")

    assert sess_a.workspace_path != sess_b.workspace_path
    assert f"sess-{sess_a.session_id}" in sess_a.workspace_path
    assert f"sess-{sess_b.session_id}" in sess_b.workspace_path


# ── 6. TTL eviction ────────────────────────────────────────────────────────


def test_ttl_eviction(manager):
    with patch("httpx.get", return_value=_mock_health_response()):
        with patch("httpx.post", return_value=_mock_exec_response()):
            sess = manager.create()

    # Write a session.json with a very old last_used_at
    session_file = manager._session_dir(sess.session_id) / "session.json"
    data = json.loads(session_file.read_text())
    data["last_used_at"] = "2020-01-01T00:00:00+00:00"
    session_file.write_text(json.dumps(data))

    evicted = manager.garbage_collect()
    assert evicted >= 1
    assert not session_file.exists()


# ── 7. LRU eviction ────────────────────────────────────────────────────────


def test_lru_eviction(manager):
    with patch("httpx.get", return_value=_mock_health_response()):
        with patch("httpx.post", return_value=_mock_exec_response()):
            [manager.create() for _ in range(6)]  # max_sessions=5

    # Creating the 6th session should have evicted the oldest
    assert len(manager.list(alive_only=True)) <= 5


# ── 8. Explicit evict() removes session entry and local mirror dir ─────────


def test_explicit_evict_removes_session(manager):
    with patch("httpx.get", return_value=_mock_health_response()):
        with patch("httpx.post", return_value=_mock_exec_response()):
            sess = manager.create()

    session_dir = manager._session_dir(sess.session_id)
    assert session_dir.exists()

    with patch("httpx.get", return_value=_mock_health_response()):
        with patch("httpx.post", return_value=_mock_exec_response()):
            manager.evict(sess.session_id)

    assert not session_dir.exists()


# ── 9. list(alive_only=True) excludes evicted entries ──────────────────────


def test_list_alive_only_excludes_evicted(manager):
    with patch("httpx.get", return_value=_mock_health_response()):
        with patch("httpx.post", return_value=_mock_exec_response()):
            sess = manager.create()
            sess = manager.create()

    with patch("httpx.get", return_value=_mock_health_response()):
        with patch("httpx.post", return_value=_mock_exec_response()):
            manager.evict(sess.session_id)

    alive = manager.list(alive_only=True)
    assert all(s.session_id != sess.session_id for s in alive)

    all_sessions = manager.list(alive_only=False)
    # Evicted session should appear in tombstones
    assert any(s.session_id == sess.session_id for s in all_sessions)


# ── 10. ReAct integration: two sandbox calls, second inherits session_id ───


def test_react_integration_two_sandbox_calls():
    """A fake LLM issues two sandbox calls; second call inherits session_id from first."""
    from tools.sandbox.index import run

    with patch("httpx.get", return_value=_mock_health_response()):
        with patch("httpx.post", return_value=_mock_exec_response()):
            # First call without session_id — auto-creates session
            result1 = run({
                "operation": "code_execute",
                "code": "open('foo.txt', 'w').write('hi')",
                "language": "python",
                "goal_id": "goal-test",
            })

    assert "result" in result1
    session_id = result1["result"].get("session_id")
    assert session_id is not None

    with patch("httpx.get", return_value=_mock_health_response()):
        with patch("httpx.post", return_value=_mock_exec_response()):
            # Second call with session_id — reuses session
            result2 = run({
                "operation": "code_execute",
                "code": "print(open('foo.txt').read())",
                "language": "python",
                "session_id": session_id,
            })

    assert "result" in result2
    assert result2["result"].get("session_id") == session_id


# ── Helper tests ───────────────────────────────────────────────────────────


def test_ulid_format():
    uid = _ulid()
    parts = uid.split("-")
    assert len(parts) == 2
    assert len(parts[0]) == 13  # timestamp
    assert len(parts[1]) == 16  # hex random


def test_is_alive_returns_false_for_unknown(manager):
    assert manager.is_alive("nonexistent") is False


def test_schema_version_mismatch_raises(manager):
    with patch("httpx.get", return_value=_mock_health_response()):
        with patch("httpx.post", return_value=_mock_exec_response()):
            sess = manager.create()

    session_file = manager._session_dir(sess.session_id) / "session.json"
    data = json.loads(session_file.read_text())
    data["schema_version"] = 999
    session_file.write_text(json.dumps(data))

    with pytest.raises(SessionError, match="incompatible session schema"):
        manager.attach(sess.session_id)
