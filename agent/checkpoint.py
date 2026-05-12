"""Checkpoint + resume for durable goal execution.

Periodic snapshots of {trace, messages, artifact registry pointers, session IDs}
written to disk; resume_goal(goal_id) re-attaches state and continues.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from agent.config import CONFIG

SCHEMA_VERSION = 1


class CheckpointError(Exception):
    pass


class IncompatibleCheckpoint(CheckpointError):
    pass


class SessionsExpired(CheckpointError):
    pass


@dataclass
class GoalCheckpoint:
    goal_id: str
    sprint_id: str | None
    goal_text: str
    step_count: int
    cost_usd: float
    messages: list[dict]
    trace_steps: list[dict]
    artifact_ids: list[str]
    sandbox_session_ids: list[str]
    browser_session_ids: list[str]
    created_at: str
    schema_version: int = SCHEMA_VERSION


_INSTANCE: CheckpointManager | None = None
_INSTANCE_LOCK = Lock()


def get_checkpoint_manager() -> CheckpointManager:
    global _INSTANCE
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            root = Path(os.path.expanduser(CONFIG.checkpoint_root))
            _INSTANCE = CheckpointManager(root=root, keep=CONFIG.checkpoint_keep)
        return _INSTANCE


class CheckpointManager:
    def __init__(
        self,
        root: Path,
        keep: int = 5,
        clock: Any = None,
    ) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.keep = keep
        self._clock = clock or time.time
        self._lock = Lock()

    def write(self, cp: GoalCheckpoint) -> Path:
        with self._lock:
            goal_dir = self._goal_dir(cp.goal_id)
            goal_dir.mkdir(parents=True, exist_ok=True)
            n = self._next_n(goal_dir)
            path = goal_dir / f"checkpoint-{n}.json"
            self._atomic_write(path, asdict(cp))
            self._update_latest(goal_dir, n)
            self._garbage_collect_locked(goal_dir)
            return path

    def load(self, goal_id: str, n: int | None = None) -> GoalCheckpoint:
        if n is not None:
            path = self._goal_dir(goal_id) / f"checkpoint-{n}.json"
        else:
            latest_n = self._read_latest(goal_id)
            if latest_n is None:
                raise CheckpointError(f"No checkpoint found for goal {goal_id}")
            path = self._goal_dir(goal_id) / f"checkpoint-{latest_n}.json"
        if not path.exists():
            raise CheckpointError(f"Checkpoint {n} not found for goal {goal_id}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema_version") != SCHEMA_VERSION:
            raise IncompatibleCheckpoint(
                f"Checkpoint schema v{data.get('schema_version')} incompatible, expected v{SCHEMA_VERSION}"
            )
        return GoalCheckpoint(**data)

    def latest(self, goal_id: str) -> GoalCheckpoint | None:
        try:
            return self.load(goal_id)
        except CheckpointError:
            return None

    def list_n(self, goal_id: str) -> list[int]:
        goal_dir = self._goal_dir(goal_id)
        if not goal_dir.exists():
            return []
        out: list[int] = []
        for f in goal_dir.iterdir():
            if f.name.startswith("checkpoint-") and f.name.endswith(".json"):
                try:
                    n = int(f.name.removeprefix("checkpoint-").removesuffix(".json"))
                    out.append(n)
                except ValueError:
                    continue
        return sorted(out)

    def collapse_to_final(self, goal_id: str) -> None:
        with self._lock:
            goal_dir = self._goal_dir(goal_id)
            latest_n = self._read_latest(goal_id)
            if latest_n is None:
                return
            latest_path = goal_dir / f"checkpoint-{latest_n}.json"
            final_path = goal_dir / "final.json"
            shutil.copy2(str(latest_path), str(final_path))
            for f in goal_dir.iterdir():
                if f.name.startswith("checkpoint-") and f.name.endswith(".json"):
                    f.unlink()
            (goal_dir / "latest.json").write_text(
                json.dumps({"latest": "final"}), encoding="utf-8"
            )

    def garbage_collect(self, goal_id: str) -> int:
        with self._lock:
            goal_dir = self._goal_dir(goal_id)
            return self._garbage_collect_locked(goal_dir)

    def _goal_dir(self, goal_id: str) -> Path:
        return self.root / goal_id

    def _next_n(self, goal_dir: Path) -> int:
        existing = self.list_n(str(goal_dir.name))
        return (existing[-1] if existing else 0) + 1

    def _atomic_write(self, path: Path, data: dict) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        tmp.replace(path)

    def _update_latest(self, goal_dir: Path, n: int) -> None:
        latest = goal_dir / "latest.json"
        tmp = latest.with_suffix(".tmp")
        tmp.write_text(json.dumps({"latest": n}), encoding="utf-8")
        tmp.replace(latest)

    def _read_latest(self, goal_id: str) -> int | None:
        latest = self._goal_dir(goal_id) / "latest.json"
        if not latest.exists():
            return None
        data = json.loads(latest.read_text(encoding="utf-8"))
        val = data.get("latest")
        if val == "final":
            return None
        return int(val) if val is not None else None

    def _garbage_collect_locked(self, goal_dir: Path) -> int:
        checkpoints = sorted(
            (f for f in goal_dir.iterdir() if f.name.startswith("checkpoint-") and f.name.endswith(".json")),
            key=lambda f: f.name,
        )
        evicted = 0
        while len(checkpoints) > self.keep:
            checkpoints.pop(0).unlink()
            evicted += 1
        return evicted


def checkpoint_now(goal_id: str, messages: list[dict], trace_steps: list[dict], artifact_ids: list[str], cost_usd: float, goal_text: str, reason: str = "periodic", sandbox_session_ids: list[str] | None = None, browser_session_ids: list[str] | None = None) -> Path:
    """Manually checkpoint the current goal state.

    Used by the reviewer or by external callers to create an on-demand
    snapshot. The ``reason`` tag is stored in the checkpoint metadata.

    """
    from datetime import datetime, timezone
    mgr = get_checkpoint_manager()
    cp = GoalCheckpoint(
        goal_id=goal_id,
        sprint_id=None,
        goal_text=goal_text,
        step_count=len(trace_steps),
        cost_usd=cost_usd,
        messages=list(messages),
        trace_steps=list(trace_steps),
        artifact_ids=list(artifact_ids),
        sandbox_session_ids=list(sandbox_session_ids or []),
        browser_session_ids=list(browser_session_ids or []),
        created_at=datetime.fromtimestamp(time.time(), tz=timezone.utc).isoformat(),
    )
    return mgr.write(cp)
