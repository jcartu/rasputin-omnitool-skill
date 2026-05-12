"""Skeleton for Phase 5: agent/checkpoint.py — durable goal state.

Snapshots are JSON files at:
    ~/.rasputin/checkpoints/<goal_id>/checkpoint-N.json
With a pointer at:
    ~/.rasputin/checkpoints/<goal_id>/latest.json   # {"latest": N}
And a final collapsed snapshot:
    ~/.rasputin/checkpoints/<goal_id>/final.json    # for approved goals

All writes are atomic (tmp + rename).
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


SCHEMA_VERSION = 1


@dataclass
class GoalCheckpoint:
    goal_id: str
    goal_text: str
    step_count: int
    cost_usd: float
    messages: list[dict]
    trace_steps: list[dict]
    artifact_ids: list[str]
    sandbox_session_ids: list[str]
    browser_session_ids: list[str]
    halted_for: Optional[str]
    created_at: str
    schema_version: int = SCHEMA_VERSION
    sprint_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class CheckpointError(Exception): ...
class IncompatibleCheckpoint(CheckpointError): ...
class CheckpointNotFound(CheckpointError): ...
class SessionsExpired(CheckpointError):
    def __init__(self, dead: list[str]):
        super().__init__(f"sessions no longer alive: {dead}")
        self.dead = dead


# ---- module-level entrypoints ----

def _root() -> Path:
    p = Path(os.path.expanduser(
        os.environ.get(
            "RASPUTIN_OMNITOOL_CHECKPOINT_ROOT",
            "~/.rasputin/checkpoints",
        )
    ))
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_checkpoint(state: GoalCheckpoint) -> Path:
    if state.schema_version != SCHEMA_VERSION:
        raise IncompatibleCheckpoint(f"unexpected schema {state.schema_version}")
    d = _root() / state.goal_id
    d.mkdir(parents=True, exist_ok=True)

    path = d / f"checkpoint-{state.step_count:05d}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(asdict(state), indent=2, default=str))
    tmp.replace(path)

    latest_tmp = d / "latest.json.tmp"
    latest = d / "latest.json"
    latest_tmp.write_text(json.dumps({"latest": state.step_count}, indent=2))
    latest_tmp.replace(latest)
    return path


def load_checkpoint(goal_id: str, n: int | None = None) -> GoalCheckpoint:
    d = _root() / goal_id
    if not d.exists():
        raise CheckpointNotFound(goal_id)
    if n is None:
        final = d / "final.json"
        if final.exists():
            return _read_one(final)
        latest_pointer = d / "latest.json"
        if not latest_pointer.exists():
            raise CheckpointNotFound(f"{goal_id}: no latest pointer")
        n = json.loads(latest_pointer.read_text())["latest"]
    path = d / f"checkpoint-{int(n):05d}.json"
    if not path.exists():
        raise CheckpointNotFound(f"{goal_id}/checkpoint-{n}")
    return _read_one(path)


def _read_one(path: Path) -> GoalCheckpoint:
    data = json.loads(path.read_text())
    if data.get("schema_version") != SCHEMA_VERSION:
        raise IncompatibleCheckpoint(
            f"checkpoint at {path} has schema {data.get('schema_version')}; expected {SCHEMA_VERSION}"
        )
    return GoalCheckpoint(**data)


def list_checkpoints(goal_id: str) -> list[int]:
    d = _root() / goal_id
    if not d.exists():
        return []
    out: list[int] = []
    for p in d.iterdir():
        if p.name.startswith("checkpoint-") and p.suffix == ".json":
            try:
                n = int(p.stem.split("-", 1)[1])
                out.append(n)
            except ValueError:
                continue
    return sorted(out)


def latest_checkpoint(goal_id: str) -> Optional[GoalCheckpoint]:
    try:
        return load_checkpoint(goal_id)
    except CheckpointNotFound:
        return None


def collapse_to_final(goal_id: str) -> None:
    """After approval, keep only final.json."""
    d = _root() / goal_id
    if not d.exists():
        return
    latest = load_checkpoint(goal_id)
    final = d / "final.json"
    tmp = d / "final.json.tmp"
    tmp.write_text(json.dumps(asdict(latest), indent=2, default=str))
    tmp.replace(final)
    for p in d.iterdir():
        if p.name in ("final.json", "final.json.tmp"):
            continue
        try:
            p.unlink()
        except IsADirectoryError:
            shutil.rmtree(p, ignore_errors=True)


def garbage_collect(keep: int = 5) -> int:
    """For every goal, keep newest `keep` numbered checkpoints + final.json."""
    removed = 0
    for d in _root().iterdir():
        if not d.is_dir():
            continue
        ns = list_checkpoints(d.name)
        if len(ns) <= keep:
            continue
        to_remove = ns[: len(ns) - keep]
        for n in to_remove:
            p = d / f"checkpoint-{n:05d}.json"
            try:
                p.unlink()
                removed += 1
            except FileNotFoundError:
                pass
    return removed


# ---- the resume entrypoint ----

def resume_goal(goal_id: str, allow_session_loss: bool = False) -> dict:
    """Public entrypoint: re-attach state and continue a goal."""
    from agent import run_goal  # local import to avoid cycle
    from agent.session_manager import get_sandbox_session_manager
    from agent.browser_session import get_browser_session_manager

    ck = latest_checkpoint(goal_id)
    if ck is None:
        raise CheckpointNotFound(goal_id)

    # verify sessions
    dead: list[str] = []
    smgr = get_sandbox_session_manager()
    for sid in ck.sandbox_session_ids:
        if not smgr.is_alive(sid):
            dead.append(f"sandbox:{sid}")
    bmgr = get_browser_session_manager()
    for sid in ck.browser_session_ids:
        try:
            bmgr.attach(sid)
        except Exception:
            dead.append(f"browser:{sid}")

    if dead and not allow_session_loss:
        raise SessionsExpired(dead)

    # delegate back to run_goal with the resume marker
    return run_goal(
        ck.goal_text,
        goal_id=goal_id,
        _resume_checkpoint=ck,
        _allow_session_loss=allow_session_loss,
    )
