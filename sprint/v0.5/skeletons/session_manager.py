"""Skeleton for Phase 3: agent/session_manager.py — SandboxSessionManager.

Sessions are local-disk-backed metadata + a workspace inside the sandbox
container. The sandbox HTTP API does not natively understand sessions; we
implement them by scoping every code_execute call's cwd to a per-session dir.
"""
from __future__ import annotations

import json
import os
import secrets
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

import httpx


SCHEMA_VERSION = 1


@dataclass
class SandboxSession:
    session_id: str
    container_id: str
    workspace_path: str           # path INSIDE the sandbox container
    created_at: str               # ISO 8601 UTC
    last_used_at: str             # ISO 8601 UTC
    goal_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ulid() -> str:
    """Lexicographically-sortable ID. Not a real ULID; close enough for our use."""
    ts = int(time.time() * 1000)
    rand = secrets.token_hex(8)
    return f"{ts:013d}-{rand}"


class SessionError(Exception):
    """Base for session-manager errors."""


class SessionDead(SessionError): ...
class SessionExpired(SessionError): ...
class SessionNotFound(SessionError): ...


class SandboxSessionManager:
    """Manage per-goal sandbox workspace sessions."""

    def __init__(
        self,
        root: Path,
        sandbox_url: str,
        ttl_min: int = 60,
        max_sessions: int = 10,
        clock: callable = time.time,
    ):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.sandbox_url = sandbox_url.rstrip("/")
        self.ttl_min = ttl_min
        self.max_sessions = max_sessions
        self._clock = clock
        self._lock = Lock()

    # ---- public API ----

    def create(self, goal_id: str | None = None) -> SandboxSession:
        with self._lock:
            self._gc_locked()
            self._enforce_lru_locked()

            session_id = _ulid()
            workspace = f"/workspace/sess-{session_id}"
            container_id = self._ensure_container_alive()

            # Pre-create the workspace dir inside the sandbox
            self._exec_in_sandbox(
                container_id, f"mkdir -p {workspace}",
                timeout=10,
            )

            sess = SandboxSession(
                session_id=session_id,
                container_id=container_id,
                workspace_path=workspace,
                created_at=_utcnow_iso(),
                last_used_at=_utcnow_iso(),
                goal_id=goal_id,
            )
            self._write(sess)
            return sess

    def attach(self, session_id: str) -> SandboxSession:
        with self._lock:
            sess = self._read(session_id)
            if not self._is_alive_locked(sess):
                raise SessionDead(f"session {session_id} container unreachable")
            sess.last_used_at = _utcnow_iso()
            self._write(sess)
            return sess

    def list(self, alive_only: bool = True) -> list[SandboxSession]:
        out: list[SandboxSession] = []
        for d in sorted(self.root.iterdir()):
            if not d.is_dir():
                continue
            sj = d / "session.json"
            if not sj.exists():
                continue
            sess = self._read(d.name)
            if alive_only and not self._is_alive_locked(sess):
                continue
            out.append(sess)
        return out

    def evict(self, session_id: str) -> None:
        with self._lock:
            self._evict_locked(session_id)

    def garbage_collect(self) -> int:
        with self._lock:
            return self._gc_locked()

    def is_alive(self, session_id: str) -> bool:
        try:
            sess = self._read(session_id)
        except SessionNotFound:
            return False
        return self._is_alive_locked(sess)

    # ---- private ----

    def _session_dir(self, session_id: str) -> Path:
        return self.root / session_id

    def _read(self, session_id: str) -> SandboxSession:
        p = self._session_dir(session_id) / "session.json"
        if not p.exists():
            raise SessionNotFound(session_id)
        data = json.loads(p.read_text())
        if data.get("schema_version") != SCHEMA_VERSION:
            raise SessionError(f"incompatible session schema: {data.get('schema_version')}")
        return SandboxSession(**data)

    def _write(self, sess: SandboxSession) -> None:
        d = self._session_dir(sess.session_id)
        d.mkdir(parents=True, exist_ok=True)
        (d / "workspace").mkdir(exist_ok=True)
        tmp = d / "session.json.tmp"
        tmp.write_text(json.dumps(asdict(sess), indent=2))
        tmp.replace(d / "session.json")

    def _evict_locked(self, session_id: str) -> None:
        sess: SandboxSession | None = None
        try:
            sess = self._read(session_id)
        except SessionNotFound:
            return
        # best-effort cleanup inside the sandbox; ignore failures
        try:
            self._exec_in_sandbox(
                sess.container_id,
                f"rm -rf {sess.workspace_path}",
                timeout=10,
                allow_failure=True,
            )
        except Exception:
            pass
        # nuke local dir
        import shutil
        shutil.rmtree(self._session_dir(session_id), ignore_errors=True)

    def _gc_locked(self) -> int:
        cutoff = self._clock() - (self.ttl_min * 60)
        evicted = 0
        for d in list(self.root.iterdir()):
            if not d.is_dir():
                continue
            sj = d / "session.json"
            if not sj.exists():
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
        sessions = self.list(alive_only=False)
        if len(sessions) < self.max_sessions:
            return
        sessions.sort(key=lambda s: s.last_used_at)
        for sess in sessions[: len(sessions) - self.max_sessions + 1]:
            self._evict_locked(sess.session_id)

    def _is_alive_locked(self, sess: SandboxSession) -> bool:
        try:
            r = httpx.get(f"{self.sandbox_url}/v1/health", timeout=3)
            if r.status_code != 200:
                return False
            # also probe that the workspace still exists
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
        """Return a container/host id. The sandbox HTTP API is multi-tenant by
        default, so 'container_id' is conceptual — we use the sandbox URL as
        the id. If you switch to one-container-per-session via Docker API,
        change this method to spawn or attach a real container.
        """
        try:
            r = httpx.get(f"{self.sandbox_url}/v1/health", timeout=3)
            r.raise_for_status()
        except Exception as exc:
            raise SessionError(f"sandbox not reachable at {self.sandbox_url}: {exc}")
        return f"shared@{self.sandbox_url}"

    def _exec_in_sandbox(
        self,
        container_id: str,
        bash_cmd: str,
        timeout: int = 30,
        allow_failure: bool = False,
    ) -> dict:
        # Use the sandbox's code_execute endpoint with bash language.
        try:
            r = httpx.post(
                f"{self.sandbox_url}/v1/code/execute",
                json={"code": bash_cmd, "language": "bash", "timeout": timeout},
                timeout=timeout + 5,
            )
            if r.status_code >= 500 and not allow_failure:
                raise SessionError(f"sandbox returned {r.status_code}")
            return r.json() if r.status_code < 500 else {"stdout": "", "stderr": r.text}
        except Exception:
            if allow_failure:
                return {"stdout": "", "stderr": "unreachable"}
            raise


# ---- singleton accessor ----

_INSTANCE: SandboxSessionManager | None = None
_INSTANCE_LOCK = Lock()


def get_sandbox_session_manager() -> SandboxSessionManager:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            root = Path(os.path.expanduser(
                os.environ.get(
                    "RASPUTIN_OMNITOOL_SESSION_ROOT",
                    "~/.rasputin/sessions/sandbox",
                )
            ))
            sandbox_url = os.environ.get(
                "RASPUTIN_OMNITOOL_SANDBOX_URL", "http://localhost:8080"
            )
            ttl = int(os.environ.get("RASPUTIN_OMNITOOL_SANDBOX_SESSION_TTL_MIN", "60"))
            cap = int(os.environ.get("RASPUTIN_OMNITOOL_SANDBOX_MAX_SESSIONS", "10"))
            _INSTANCE = SandboxSessionManager(
                root=root,
                sandbox_url=sandbox_url,
                ttl_min=ttl,
                max_sessions=cap,
            )
        return _INSTANCE
