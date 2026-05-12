"""Persistent sandbox session management.

Sessions are local-disk-backed metadata plus a workspace directory inside the
sandbox service. The sandbox HTTP API has no native session primitive, so the
manager scopes each session by using a per-session ``cwd`` for code execution.
"""
from __future__ import annotations

import json
import os
import secrets
import shutil
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

import httpx

from agent.config import CONFIG

SCHEMA_VERSION = 1


@dataclass
class SandboxSession:
    """Metadata for a persistent sandbox workspace session."""

    session_id: str
    container_id: str
    workspace_path: str
    created_at: str
    last_used_at: str
    goal_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION


def _ulid() -> str:
    """Return a lexicographically sortable ID close enough for session use."""

    ts = int(time.time() * 1000)
    rand = secrets.token_hex(8)
    return f"{ts:013d}-{rand}"


class SessionError(Exception):
    """Base class for session-manager errors."""


class SessionDead(SessionError):
    """The session metadata exists, but the sandbox/workspace is gone."""


class SessionExpired(SessionError):
    """The requested session expired."""


class SessionNotFound(SessionError):
    """No session metadata exists for the requested ID."""


class SandboxSessionManager:
    """Manage per-goal sandbox workspace sessions."""

    def __init__(
        self,
        root: Path,
        sandbox_url: str,
        ttl_min: int = 60,
        max_sessions: int = 10,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.sandbox_url = sandbox_url.rstrip("/")
        self.ttl_min = ttl_min
        self.max_sessions = max_sessions
        self._clock = clock
        self._lock = Lock()
        self._evicted: dict[str, SandboxSession] = {}

    def create(self, goal_id: str | None = None) -> SandboxSession:
        """Create a new sandbox session and pre-create its workspace."""

        with self._lock:
            self._gc_locked()
            self._enforce_lru_locked()

            session_id = _ulid()
            workspace = f"/workspace/sess-{session_id}"
            container_id = self._ensure_container_alive()

            self._exec_in_sandbox(container_id, f"mkdir -p {workspace}", timeout=10)

            now = self._now_iso()
            sess = SandboxSession(
                session_id=session_id,
                container_id=container_id,
                workspace_path=workspace,
                created_at=now,
                last_used_at=now,
                goal_id=goal_id,
            )
            self._write(sess)
            self._evicted.pop(session_id, None)
            return sess

    def attach(self, session_id: str) -> SandboxSession:
        """Attach to a live session, updating its last-used timestamp."""

        with self._lock:
            sess = self._read(session_id)
            if not self._is_alive_locked(sess):
                self._evict_locked(session_id, cleanup_sandbox=False)
                raise SessionDead(f"SESSION_DEAD: session {session_id} is unreachable")
            sess.last_used_at = self._now_iso()
            self._write(sess)
            return sess

    def list(self, alive_only: bool = True) -> list[SandboxSession]:
        """List known sessions; optionally include this-process tombstones."""

        with self._lock:
            return self._list_locked(alive_only=alive_only)

    def evict(self, session_id: str) -> None:
        """Explicitly evict a session and remove its local mirror directory."""

        with self._lock:
            self._evict_locked(session_id)

    def garbage_collect(self) -> int:
        """Evict sessions idle longer than the configured TTL."""

        with self._lock:
            return self._gc_locked()

    def is_alive(self, session_id: str) -> bool:
        """Return whether a session exists and its sandbox workspace is live."""

        try:
            sess = self._read(session_id)
        except SessionNotFound:
            return False
        return self._is_alive_locked(sess)

    def _now_iso(self) -> str:
        return datetime.fromtimestamp(self._clock(), timezone.utc).isoformat()

    def _session_dir(self, session_id: str) -> Path:
        return self.root / session_id

    def _read(self, session_id: str) -> SandboxSession:
        p = self._session_dir(session_id) / "session.json"
        if not p.exists():
            raise SessionNotFound(session_id)
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("schema_version") != SCHEMA_VERSION:
            raise SessionError(f"incompatible session schema: {data.get('schema_version')}")
        return SandboxSession(**data)

    def _write(self, sess: SandboxSession) -> None:
        d = self._session_dir(sess.session_id)
        d.mkdir(parents=True, exist_ok=True)
        (d / "workspace").mkdir(exist_ok=True)
        tmp = d / "session.json.tmp"
        tmp.write_text(json.dumps(asdict(sess), indent=2), encoding="utf-8")
        tmp.replace(d / "session.json")

    def _list_locked(self, alive_only: bool) -> list[SandboxSession]:
        out: list[SandboxSession] = []
        for d in sorted(self.root.iterdir()):
            if not d.is_dir() or not (d / "session.json").exists():
                continue
            sess = self._read(d.name)
            if alive_only and not self._is_alive_locked(sess):
                continue
            out.append(sess)
        if not alive_only:
            out.extend(self._evicted.values())
        return out

    def _evict_locked(self, session_id: str, cleanup_sandbox: bool = True) -> None:
        try:
            sess = self._read(session_id)
        except SessionNotFound:
            return

        self._evicted[session_id] = sess
        if cleanup_sandbox:
            try:
                self._exec_in_sandbox(
                    sess.container_id,
                    f"rm -rf {sess.workspace_path}",
                    timeout=10,
                    allow_failure=True,
                )
            except Exception:
                pass
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
        sessions = [sess for sess in self._list_locked(alive_only=False) if sess.session_id not in self._evicted]
        if len(sessions) < self.max_sessions:
            return
        sessions.sort(key=lambda s: s.last_used_at)
        for sess in sessions[: len(sessions) - self.max_sessions + 1]:
            self._evict_locked(sess.session_id)

    def _is_alive_locked(self, sess: SandboxSession) -> bool:
        try:
            r = httpx.get(f"{self.sandbox_url}/v1/code/info", timeout=3)
            if r.status_code != 200:
                return False
            res = self._exec_in_sandbox(
                sess.container_id,
                f"test -d {sess.workspace_path} && echo OK || echo MISSING",
                timeout=5,
                allow_failure=True,
            )
            return "OK" in res.get("stdout", "")
        except Exception:
            return False

    def _ensure_container_alive(self) -> str:
        """Return a conceptual container ID for the shared sandbox API host."""
        try:
            r = httpx.get(f"{self.sandbox_url}/v1/code/info", timeout=3)
            if r.status_code != 200:
                raise SessionError(f"sandbox not reachable at {self.sandbox_url}: HTTP {r.status_code}")
        except httpx.HTTPError:
            raise
        except Exception as exc:
            raise SessionError(f"sandbox not reachable at {self.sandbox_url}: {exc}") from exc
        return f"shared@{self.sandbox_url}"

    def _exec_in_sandbox(
        self,
        container_id: str,
        bash_cmd: str,
        timeout: int = 30,
        allow_failure: bool = False,
    ) -> dict[str, Any]:
        del container_id
        try:
            r = httpx.post(
                f"{self.sandbox_url}/v1/shell/exec",
                json={"command": bash_cmd, "timeout": timeout},
                timeout=timeout + 5,
            )
            if r.status_code >= 500 and not allow_failure:
                raise SessionError(f"sandbox returned {r.status_code}")
            data = r.json()
            # New API format: data.output contains stdout
            if data.get("success"):
                return {"stdout": data.get("data", {}).get("output", ""), "stderr": "", "exit_code": data.get("data", {}).get("exit_code", 0)}
            return {"stdout": "", "stderr": data.get("message", r.text), "exit_code": -1}
        except Exception:
            if allow_failure:
                return {"stdout": "", "stderr": "unreachable"}
            raise


_INSTANCE: SandboxSessionManager | None = None
_INSTANCE_LOCK = Lock()


def get_sandbox_session_manager() -> SandboxSessionManager:
    """Return the process-wide sandbox session manager."""

    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            root = Path(os.path.expanduser(CONFIG.session_root))
            _INSTANCE = SandboxSessionManager(
                root=root,
                sandbox_url=CONFIG.sandbox_url,
                ttl_min=CONFIG.sandbox_session_ttl_min,
                max_sessions=CONFIG.sandbox_max_sessions,
            )
        return _INSTANCE
