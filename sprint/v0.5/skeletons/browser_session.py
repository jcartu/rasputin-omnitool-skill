"""Skeleton for Phase 4: agent/browser_session.py — BrowserSessionManager.

Uses Playwright's persistent context (user_data_dir) as the source of truth
for session state. Each tool call launches a fresh persistent context against
the session's user_data_dir, runs the action, and closes. Storage state is
snapshotted as a recovery fallback after every action.
"""
from __future__ import annotations

import json
import os
import secrets
import shutil
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional, TypeVar

SCHEMA_VERSION = 1

T = TypeVar("T")


@dataclass
class BrowserSession:
    session_id: str
    user_data_dir: str            # absolute path on host
    storage_state_path: str       # absolute path; recovery snapshot
    created_at: str
    last_used_at: str
    last_url: Optional[str] = None
    goal_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ulid() -> str:
    ts = int(time.time() * 1000)
    rand = secrets.token_hex(8)
    return f"{ts:013d}-{rand}"


class BrowserSessionError(Exception): ...
class BrowserSessionNotFound(BrowserSessionError): ...
class BrowserSessionDead(BrowserSessionError): ...


class BrowserSessionManager:
    def __init__(
        self,
        root: Path,
        ttl_min: int = 60,
        max_sessions: int = 10,
        headless: bool = True,
    ):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.ttl_min = ttl_min
        self.max_sessions = max_sessions
        self.headless = headless
        self._lock = Lock()

    # ---- public API ----

    def create(self, goal_id: str | None = None) -> BrowserSession:
        with self._lock:
            self._gc_locked()
            self._enforce_lru_locked()

            session_id = _ulid()
            d = self._session_dir(session_id)
            d.mkdir(parents=True, exist_ok=True)
            (d / "user_data").mkdir(exist_ok=True)
            (d / "screenshots").mkdir(exist_ok=True)

            sess = BrowserSession(
                session_id=session_id,
                user_data_dir=str((d / "user_data").resolve()),
                storage_state_path=str((d / "storage_state.json").resolve()),
                created_at=_utcnow_iso(),
                last_used_at=_utcnow_iso(),
                goal_id=goal_id,
            )
            self._write(sess)
            return sess

    def attach(self, session_id: str) -> BrowserSession:
        with self._lock:
            sess = self._read(session_id)
            if not Path(sess.user_data_dir).exists():
                raise BrowserSessionDead(f"user_data_dir missing for {session_id}")
            sess.last_used_at = _utcnow_iso()
            self._write(sess)
            return sess

    def list(self, alive_only: bool = True) -> list[BrowserSession]:
        out: list[BrowserSession] = []
        for d in sorted(self.root.iterdir()):
            if not d.is_dir():
                continue
            if not (d / "session.json").exists():
                continue
            sess = self._read(d.name)
            if alive_only and not Path(sess.user_data_dir).exists():
                continue
            out.append(sess)
        return out

    def evict(self, session_id: str) -> None:
        with self._lock:
            self._evict_locked(session_id)

    def garbage_collect(self) -> int:
        with self._lock:
            return self._gc_locked()

    @contextmanager
    def page_for(self, session: BrowserSession):
        """Context manager yielding a Playwright Page bound to this session.

        Usage:
            with mgr.page_for(sess) as page:
                page.goto(url)
                ...
            # on exit, storage_state is snapshotted and the browser is closed.
        """
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=session.user_data_dir,
                headless=self.headless,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
                accept_downloads=False,
            )
            try:
                page = context.new_page() if not context.pages else context.pages[0]
                page.set_default_timeout(30000)
                yield page
            finally:
                # snapshot storage_state for recovery
                try:
                    context.storage_state(path=session.storage_state_path)
                except Exception:
                    pass
                try:
                    context.close()
                except Exception:
                    pass
                # update last_used_at + last_url
                with self._lock:
                    try:
                        fresh = self._read(session.session_id)
                        fresh.last_used_at = _utcnow_iso()
                        try:
                            fresh.last_url = page.url
                        except Exception:
                            pass
                        self._write(fresh)
                    except BrowserSessionNotFound:
                        pass

    def screenshot_path(self, session: BrowserSession, name: str | None = None) -> Path:
        d = Path(self._session_dir(session.session_id) / "screenshots")
        d.mkdir(parents=True, exist_ok=True)
        if name is None:
            name = f"shot-{int(time.time()*1000)}.png"
        elif not name.endswith(".png"):
            name = f"{name}.png"
        return d / name

    # ---- private ----

    def _session_dir(self, session_id: str) -> Path:
        return self.root / session_id

    def _read(self, session_id: str) -> BrowserSession:
        p = self._session_dir(session_id) / "session.json"
        if not p.exists():
            raise BrowserSessionNotFound(session_id)
        data = json.loads(p.read_text())
        if data.get("schema_version") != SCHEMA_VERSION:
            raise BrowserSessionError(f"incompatible session schema: {data.get('schema_version')}")
        return BrowserSession(**data)

    def _write(self, sess: BrowserSession) -> None:
        d = self._session_dir(sess.session_id)
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "session.json.tmp"
        tmp.write_text(json.dumps(asdict(sess), indent=2))
        tmp.replace(d / "session.json")

    def _evict_locked(self, session_id: str) -> None:
        d = self._session_dir(session_id)
        shutil.rmtree(d, ignore_errors=True)

    def _gc_locked(self) -> int:
        cutoff = datetime.now(timezone.utc).timestamp() - (self.ttl_min * 60)
        evicted = 0
        for d in list(self.root.iterdir()):
            if not d.is_dir() or not (d / "session.json").exists():
                continue
            try:
                sess = self._read(d.name)
            except BrowserSessionError:
                continue
            last = datetime.fromisoformat(sess.last_used_at).timestamp()
            if last < cutoff:
                self._evict_locked(sess.session_id)
                evicted += 1
        return evicted

    def _enforce_lru_locked(self) -> None:
        sessions = self.list(alive_only=False)
        if len(sessions) < self.max_sessions:
            return
        sessions.sort(key=lambda s: s.last_used_at)
        for sess in sessions[: len(sessions) - self.max_sessions + 1]:
            self._evict_locked(sess.session_id)


# ---- singleton accessor ----

_INSTANCE: BrowserSessionManager | None = None
_INSTANCE_LOCK = Lock()


def get_browser_session_manager() -> BrowserSessionManager:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            root = Path(os.path.expanduser(
                os.environ.get(
                    "RASPUTIN_OMNITOOL_BROWSER_SESSION_ROOT",
                    "~/.rasputin/sessions/browser",
                )
            ))
            ttl = int(os.environ.get("RASPUTIN_OMNITOOL_BROWSER_SESSION_TTL_MIN", "60"))
            cap = int(os.environ.get("RASPUTIN_OMNITOOL_BROWSER_MAX_SESSIONS", "10"))
            headless = os.environ.get("RASPUTIN_OMNITOOL_BROWSER_HEADLESS", "1") == "1"
            _INSTANCE = BrowserSessionManager(
                root=root, ttl_min=ttl, max_sessions=cap, headless=headless,
            )
        return _INSTANCE
