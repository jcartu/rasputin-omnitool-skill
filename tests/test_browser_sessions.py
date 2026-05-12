"""Unit tests for persistent browser sessions."""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.browser_session import (
    BrowserSessionManager,
    SessionNotFound,
)


@pytest.fixture
def tmp_root(tmp_path: Path) -> Path:
    return tmp_path / "browser_sessions"


@pytest.fixture
def manager(tmp_root: Path):
    mgr = BrowserSessionManager(
        root=tmp_root,
        ttl_min=60,
        max_sessions=5,
        clock=time.time,
    )
    return mgr


# ── 1. create() generates user_data_dir + writes session.json ─────────────

def test_create_generates_dirs_and_session_json(manager):
    sess = manager.create()

    assert sess.session_id
    assert Path(sess.user_data_dir).is_dir()
    assert Path(sess.screenshots_dir).is_dir()
    assert (manager._session_dir(sess.session_id) / "session.json").exists()

    data = json.loads((manager._session_dir(sess.session_id) / "session.json").read_text())
    assert data["session_id"] == sess.session_id
    assert data["schema_version"] == 1


def test_create_with_goal_id(manager):
    sess = manager.create(goal_id="goal-123")
    assert sess.goal_id == "goal-123"


# ── 2. attach() succeeds on live session; fails if user_data_dir missing ──

def test_attach_succeeds_for_live_session(manager):
    sess = manager.create()
    attached = manager.attach(sess.session_id)
    assert attached.session_id == sess.session_id
    assert attached.user_data_dir == sess.user_data_dir


def test_attach_fails_for_unknown_id(manager):
    with pytest.raises(SessionNotFound):
        manager.attach("nonexistent-id")


def test_attach_fails_when_user_data_dir_missing(manager):
    sess = manager.create()
    import shutil
    shutil.rmtree(sess.user_data_dir)
    with pytest.raises(SessionNotFound, match="user_data_dir missing"):
        manager.attach(sess.session_id)


# ── 3. Cross-session isolation ─────────────────────────────────────────────

def test_cross_session_isolation(manager):
    sess_a = manager.create()
    sess_b = manager.create()
    assert sess_a.user_data_dir != sess_b.user_data_dir
    assert sess_a.session_id != sess_b.session_id


# ── 4. storage_state save/load ─────────────────────────────────────────────

def test_storage_state_save_and_load(manager):
    sess = manager.create()
    state = {"origins": [{"origin": "https://example.com", "cookies": [{"name": "demo", "value": "v05"}]}]}
    manager.save_storage_state(sess.session_id, state)
    loaded = manager.load_storage_state(sess.session_id)
    assert loaded == state


def test_storage_state_missing_returns_none(manager):
    sess = manager.create()
    assert manager.load_storage_state(sess.session_id) is None


# ── 5. TTL eviction ─────────────────────────────────────────────

def test_ttl_eviction_removes_old_sessions(manager):
    sess = manager.create()
    # Backdate the session
    import datetime
    sess.last_used_at = datetime.datetime.fromtimestamp(time.time() - 7200, tz=datetime.timezone.utc).isoformat()
    manager._write(sess)
    assert manager.garbage_collect() == 1
    assert not Path(sess.user_data_dir).exists()


# ── 6. LRU eviction ────────────────────────────────────────────────────────

def test_lru_eviction_at_cap(manager):
    sessions = []
    for i in range(7):
        s = manager.create()
        time.sleep(0.01)
        sessions.append(s)
    # max_sessions is 5, so 2 oldest should be evicted on next create
    manager.create()
    alive = manager.list()
    assert len(alive) <= 5


# ── 7. list() and evict() ──────────────────────────────────────────────────

def test_list_returns_created_sessions(manager):
    manager.create()
    manager.create()
    assert len(manager.list()) == 2


def test_evict_removes_session(manager):
    sess = manager.create()
    manager.evict(sess.session_id)
    assert not Path(sess.user_data_dir).exists()
    assert len(manager.list()) == 0


# ── 8. run_action with mock Playwright ─────────────────────────────────────

def test_run_action_returns_result_and_storage_state(manager):
    sess = manager.create()

    mock_page = MagicMock()
    mock_page.title.return_value = "Test"
    mock_page.url = "https://example.com"

    mock_context = MagicMock()
    mock_context.pages = [mock_page]

    mock_storage = {"origins": []}
    mock_context.storage_state.return_value = mock_storage

    mock_chromium = MagicMock()
    mock_chromium.launch_persistent_context.return_value = mock_context

    mock_pw = MagicMock()
    mock_pw.chromium = mock_chromium

    mock_ctx_mgr = MagicMock()
    mock_ctx_mgr.__enter__.return_value = mock_pw
    mock_ctx_mgr.__exit__.return_value = None

    with patch("playwright.sync_api.sync_playwright", return_value=mock_ctx_mgr):
        result, storage = manager.run_action(sess, lambda page: {"title": page.title()})

    assert result == {"title": "Test"}
    assert storage == mock_storage
    mock_context.close.assert_called_once()


# ── 9. evaluate action returns JSON-serializable value ─────────────────────

def test_evaluate_returns_value(manager):
    sess = manager.create()
    mock_page = MagicMock()
    mock_page.evaluate.return_value = 42
    mock_context = MagicMock()
    mock_context.pages = [mock_page]
    mock_context.storage_state.return_value = {}
    mock_chromium = MagicMock()
    mock_chromium.launch_persistent_context.return_value = mock_context
    mock_pw = MagicMock()
    mock_pw.chromium = mock_chromium
    mock_ctx_mgr = MagicMock()
    mock_ctx_mgr.__enter__.return_value = mock_pw
    mock_ctx_mgr.__exit__.return_value = None

    with patch("playwright.sync_api.sync_playwright", return_value=mock_ctx_mgr):
        result, _ = manager.run_action(sess, lambda page: {"result": page.evaluate("2+2")})

    assert result == {"result": 42}

def test_storage_state_written_after_run_action(manager):
    sess = manager.create()
    storage_path = Path(sess.storage_state_path)
    assert not storage_path.exists()

    mock_page = MagicMock()
    mock_page.evaluate.return_value = 1
    mock_context = MagicMock()
    mock_context.pages = [mock_page]
    mock_context.storage_state.return_value = {"origins": [{"origin": "https://example.com"}]}
    mock_context.add_cookies = MagicMock()
    mock_chromium = MagicMock()
    mock_chromium.launch_persistent_context.return_value = mock_context
    mock_pw = MagicMock()
    mock_pw.chromium = mock_chromium
    mock_ctx_mgr = MagicMock()
    mock_ctx_mgr.__enter__.return_value = mock_pw
    mock_ctx_mgr.__exit__.return_value = None

    with patch("playwright.sync_api.sync_playwright", return_value=mock_ctx_mgr):
        _, storage = manager.run_action(sess, lambda page: {"result": page.evaluate("1")})
        manager.save_storage_state(sess.session_id, storage)

    assert storage_path.exists()
    data = __import__("json").loads(storage_path.read_text())
    assert "origins" in data


def test_evaluate_non_serializable_returns_error(manager):
    sess = manager.create()
    mock_page = MagicMock()
    mock_page.evaluate.side_effect = TypeError("cannot serialize")
    mock_context = MagicMock()
    mock_context.pages = [mock_page]
    mock_context.storage_state.return_value = {}
    mock_context.add_cookies = MagicMock()
    mock_chromium = MagicMock()
    mock_chromium.launch_persistent_context.return_value = mock_context
    mock_pw = MagicMock()
    mock_pw.chromium = mock_chromium
    mock_ctx_mgr = MagicMock()
    mock_ctx_mgr.__enter__.return_value = mock_pw
    mock_ctx_mgr.__exit__.return_value = None

    with patch("playwright.sync_api.sync_playwright", return_value=mock_ctx_mgr):
        with pytest.raises(TypeError, match="cannot serialize"):
            manager.run_action(sess, lambda page: {"result": page.evaluate("undefined")})

    # Tool layer (_classify_error) catches TypeError and returns NAVIGATION_FAILED
    from tools.browser.index import _classify_error
    result = _classify_error(TypeError("cannot serialize"), "evaluate")
    assert result.get("error", {}).get("code") == "NAVIGATION_FAILED"
