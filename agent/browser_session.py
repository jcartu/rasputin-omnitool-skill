"""Persistent browser session management.

Sessions use Playwright's `launch_persistent_context` with a per-session
user_data_dir so cookies, localStorage, and auth tokens persist across tool
calls. Each tool call launches a fresh context against the user_data_dir,
runs the action, snapshots storage_state, then closes.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, TypeVar

from agent.config import CONFIG
from agent.session_manager import SessionError, SessionNotFound, _ulid

SCHEMA_VERSION = 1

T = TypeVar("T")


@dataclass
class BrowserSession:
    """Metadata for a persistent browser session."""

    session_id: str
    user_data_dir: str
    storage_state_path: str
    screenshots_dir: str
    created_at: str
    last_used_at: str
    goal_id: str | None = None
    last_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION


class BrowserSessionManager:
    """Manage per-goal browser sessions with persistent user_data_dir."""

    def __init__(
        self,
        root: Path,
        ttl_min: int = 60,
        max_sessions: int = 10,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.ttl_min = ttl_min
        self.max_sessions = max_sessions
        self._clock = clock
        self._lock = Lock()
        self._evicted: dict[str, BrowserSession] = {}

    def create(self, goal_id: str | None = None) -> BrowserSession:
        """Create a new browser session with a fresh user_data_dir."""
        with self._lock:
            self._gc_locked()
            self._enforce_lru_locked()

            session_id = _ulid()
            user_data_dir = self._session_dir(session_id) / "user_data"
            user_data_dir.mkdir(parents=True, exist_ok=True)
            screenshots_dir = self._session_dir(session_id) / "screenshots"
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            storage_state_path = str(self._session_dir(session_id) / "storage_state.json")

            now = self._now_iso()
            sess = BrowserSession(
                session_id=session_id,
                user_data_dir=str(user_data_dir),
                storage_state_path=storage_state_path,
                screenshots_dir=str(screenshots_dir),
                created_at=now,
                last_used_at=now,
                goal_id=goal_id,
            )
            self._write(sess)
            self._evicted.pop(session_id, None)
            return sess

    def attach(self, session_id: str) -> BrowserSession:
        """Attach to an existing browser session."""
        with self._lock:
            sess = self._read(session_id)
            # Verify user_data_dir exists
            if not Path(sess.user_data_dir).is_dir():
                self._evict_locked(session_id)
                raise SessionNotFound(
                    f"SESSION_NOT_FOUND: browser session {session_id} user_data_dir missing"
                )
            sess.last_used_at = self._now_iso()
            self._write(sess)
            return sess

    def list(self, alive_only: bool = True) -> list[BrowserSession]:
        """List known browser sessions."""
        with self._lock:
            return self._list_locked(alive_only=alive_only)

    def evict(self, session_id: str) -> None:
        """Explicitly evict a session and remove its user_data_dir."""
        with self._lock:
            self._evict_locked(session_id)

    def garbage_collect(self) -> int:
        """Evict sessions idle longer than the configured TTL."""
        with self._lock:
            return self._gc_locked()

    def save_storage_state(self, session_id: str, state: dict[str, Any]) -> None:
        """Save Playwright storage_state JSON for a session."""
        with self._lock:
            try:
                sess = self._read(session_id)
            except SessionNotFound:
                return
            p = Path(sess.storage_state_path)
            tmp = p.with_suffix(".tmp")
            tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
            tmp.replace(p)

    def load_storage_state(self, session_id: str) -> dict[str, Any] | None:
        """Load saved storage_state JSON for a session (if available)."""
        with self._lock:
            try:
                sess = self._read(session_id)
            except SessionNotFound:
                return None
            p = Path(sess.storage_state_path)
            if not p.exists():
                return None
            return json.loads(p.read_text(encoding="utf-8"))

    def run_action(
        self, session: BrowserSession, fn: Callable[[Any], T]
    ) -> tuple[T, dict[str, Any]]:
        from playwright.sync_api import sync_playwright

        storage_state: dict[str, Any] = {}
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=session.user_data_dir,
                headless=True,
                args=["--no-sandbox"],
            )
            try:
                # Restore cookies from previous storage state
                prev_state = self.load_storage_state(session.session_id)
                if prev_state and prev_state.get("cookies"):
                    context.add_cookies(prev_state["cookies"])
                page = context.pages[0] if context.pages else context.new_page()
                page.set_default_timeout(30000)
                result = fn(page)
                storage_state = context.storage_state()
                return result, storage_state
            finally:
                context.close()

    def _now_iso(self) -> str:
        return datetime.fromtimestamp(self._clock(), timezone.utc).isoformat()

    def _session_dir(self, session_id: str) -> Path:
        return self.root / session_id

    def _read(self, session_id: str) -> BrowserSession:
        p = self._session_dir(session_id) / "session.json"
        if not p.exists():
            raise SessionNotFound(session_id)
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("schema_version") != SCHEMA_VERSION:
            raise SessionError(f"incompatible session schema: {data.get('schema_version')}")
        return BrowserSession(**data)

    def _write(self, sess: BrowserSession) -> None:
        d = self._session_dir(sess.session_id)
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "session.json.tmp"
        tmp.write_text(json.dumps(asdict(sess), indent=2), encoding="utf-8")
        tmp.replace(d / "session.json")

    def _list_locked(self, alive_only: bool) -> list[BrowserSession]:
        out: list[BrowserSession] = []
        for d in sorted(self.root.iterdir()):
            if not d.is_dir() or not (d / "session.json").exists():
                continue
            sess = self._read(d.name)
            out.append(sess)
        if not alive_only:
            out.extend(self._evicted.values())
        return out

    def _evict_locked(self, session_id: str) -> None:
        try:
            sess = self._read(session_id)
        except SessionNotFound:
            return
        self._evicted[session_id] = sess
        shutil.rmtree(self._session_dir(session_id), ignore_errors=True)

    def _gc_locked(self) -> int:
        cutoff = self._clock() - (self.ttl_min * 60)
        evicted = 0
        for d in list(self.root.iterdir()):
            if not d.is_dir() or not (d / "session.json").exists():
                continue
            try:
                sess = self._read(d.name)
            except SessionError:
                continue
            last_used_epoch = datetime.fromisoformat(sess.last_used_at).timestamp()
            if last_used_epoch < cutoff:
                self._evict_locked(sess.session_id)
                evicted += 1
        return evicted

    def _enforce_lru_locked(self) -> None:
        sessions = [
            sess
            for sess in self._list_locked(alive_only=False)
            if sess.session_id not in self._evicted
        ]
        if len(sessions) < self.max_sessions:
            return
        sessions.sort(key=lambda s: s.last_used_at)
        for sess in sessions[: len(sessions) - self.max_sessions + 1]:
            self._evict_locked(sess.session_id)


_BROWSER_INSTANCE: BrowserSessionManager | None = None
_BROWSER_INSTANCE_LOCK = Lock()


def get_browser_session_manager() -> BrowserSessionManager:
    """Return the process-wide browser session manager."""
    global _BROWSER_INSTANCE
    with _BROWSER_INSTANCE_LOCK:
        if _BROWSER_INSTANCE is None:
            root = Path(os.path.expanduser(CONFIG.browser_session_root))
            _BROWSER_INSTANCE = BrowserSessionManager(
                root=root,
                ttl_min=CONFIG.browser_session_ttl_min,
                max_sessions=CONFIG.browser_max_sessions,
            )
        return _BROWSER_INSTANCE
