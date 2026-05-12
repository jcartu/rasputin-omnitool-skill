"""orchestration/state_helpers.py — atomic state.json read/write.

The single source of truth for sprint progress. Used by run_phase.sh,
review_with_opus.sh, final_review.sh.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


STATE_PATH = Path("sprint/v0.5/state.json")


DEFAULT_STATE = {
    "sprint": "v0.5",
    "started_at": None,
    "current_phase": 0,
    "phase_status": {},
    "halt_reason": None,
    "total_cost_usd": 0.0,
    "budget_usd": float(os.environ.get("RASPUTIN_OMNITOOL_SPRINT_BUDGET_USD", "25.00")),
    "branches": {},
    "sprint_complete": False,
    "completed_at": None,
    "released_tag": None,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_state() -> dict:
    if not STATE_PATH.exists():
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        state = dict(DEFAULT_STATE)
        state["started_at"] = _now()
        write_state(state)
        return state
    return json.loads(STATE_PATH.read_text())


def write_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=False))
    tmp.replace(STATE_PATH)


def update_state(**kwargs) -> dict:
    s = read_state()
    s.update(kwargs)
    write_state(s)
    return s


def set_phase_status(phase: int, **fields) -> dict:
    s = read_state()
    ps = s.setdefault("phase_status", {})
    entry = ps.setdefault(str(phase), {"status": "not_started", "review_count": 0, "commit": None})
    entry.update(fields)
    write_state(s)
    return s


def add_cost(usd: float) -> dict:
    s = read_state()
    s["total_cost_usd"] = round(s.get("total_cost_usd", 0.0) + usd, 4)
    write_state(s)
    return s


def is_phase_approved(phase: int) -> bool:
    s = read_state()
    return s.get("phase_status", {}).get(str(phase), {}).get("status") == "approved"


def is_phase_halted(phase: int) -> bool:
    s = read_state()
    return s.get("phase_status", {}).get(str(phase), {}).get("status") == "halted"


def cli() -> int:
    """Tiny CLI for shell scripts."""
    if len(sys.argv) < 2:
        print("usage: state_helpers.py {read|set-phase|add-cost|is-approved|is-halted}", file=sys.stderr)
        return 2
    cmd = sys.argv[1]
    if cmd == "read":
        print(json.dumps(read_state(), indent=2))
        return 0
    if cmd == "set-phase":
        # set-phase N status [commit_sha]
        phase = int(sys.argv[2])
        status = sys.argv[3]
        kwargs = {"status": status}
        if len(sys.argv) > 4:
            kwargs["commit"] = sys.argv[4]
        set_phase_status(phase, **kwargs)
        return 0
    if cmd == "increment-review":
        phase = int(sys.argv[2])
        s = read_state()
        ps = s.setdefault("phase_status", {}).setdefault(str(phase), {"status": "in_progress", "review_count": 0, "commit": None})
        ps["review_count"] = ps.get("review_count", 0) + 1
        write_state(s)
        print(ps["review_count"])
        return 0
    if cmd == "add-cost":
        add_cost(float(sys.argv[2]))
        return 0
    if cmd == "is-approved":
        return 0 if is_phase_approved(int(sys.argv[2])) else 1
    if cmd == "is-halted":
        return 0 if is_phase_halted(int(sys.argv[2])) else 1
    if cmd == "halt":
        # halt N reason
        phase = int(sys.argv[2])
        reason = sys.argv[3] if len(sys.argv) > 3 else "unspecified"
        set_phase_status(phase, status="halted")
        s = read_state()
        s["halt_reason"] = reason
        write_state(s)
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(cli())
