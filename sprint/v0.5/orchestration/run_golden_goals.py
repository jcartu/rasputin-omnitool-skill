"""orchestration/run_golden_goals.py — drive the golden goal suite end-to-end.

Loads goals from tests/golden_goals.yaml, runs each against the real agent,
checks per-goal acceptance criteria, writes a results table.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("error: pyyaml required. pip install pyyaml", file=sys.stderr)
    sys.exit(78)


def load_goals(path: Path) -> list[dict]:
    return yaml.safe_load(path.read_text())["goals"]


def run_one(goal_spec: dict) -> dict:
    from agent import run_goal

    name = goal_spec["name"]
    text = goal_spec["goal"]
    timeout_min = int(goal_spec.get("timeout_min", 10))
    expect = goal_spec.get("expect", {})

    started = time.time()
    try:
        result = run_goal(
            text,
            goal_id=f"golden-{name}",
            _budget_usd=float(goal_spec.get("budget_usd", 0.50)),
            _max_wallclock_min=timeout_min,
        )
    except Exception as exc:
        return {
            "name": name,
            "status": "exception",
            "verdict": None,
            "wallclock_s": time.time() - started,
            "error": f"{type(exc).__name__}: {exc}",
        }

    elapsed = time.time() - started
    verdict = getattr(result.get("review"), "verdict", None) if result.get("review") else None
    artifacts = result.get("artifacts", [])
    cost = float(result.get("cost_usd", 0.0))

    # Per-goal acceptance
    ok = True
    failures: list[str] = []

    if "verdict" in expect and verdict != expect["verdict"]:
        ok = False
        failures.append(f"verdict={verdict} != expected {expect['verdict']}")

    if "min_artifacts" in expect and len(artifacts) < expect["min_artifacts"]:
        ok = False
        failures.append(f"artifacts={len(artifacts)} < {expect['min_artifacts']}")

    if "max_cost_usd" in expect and cost > expect["max_cost_usd"]:
        ok = False
        failures.append(f"cost ${cost:.4f} > ${expect['max_cost_usd']:.4f}")

    if "max_wallclock_s" in expect and elapsed > expect["max_wallclock_s"]:
        ok = False
        failures.append(f"wallclock {elapsed:.1f}s > {expect['max_wallclock_s']:.1f}s")

    return {
        "name": name,
        "status": "pass" if ok else "fail",
        "verdict": verdict,
        "artifacts_count": len(artifacts),
        "cost_usd": cost,
        "wallclock_s": round(elapsed, 1),
        "failures": failures,
    }


def main() -> int:
    yaml_path = Path("tests/golden_goals.yaml")
    if not yaml_path.exists():
        yaml_path = Path("sprint/v0.5/tests/golden_goals.yaml")
    if not yaml_path.exists():
        print(f"missing golden_goals.yaml at {yaml_path}", file=sys.stderr)
        return 2

    goals = load_goals(yaml_path)
    print(f"running {len(goals)} golden goals\n")

    results: list[dict] = []
    for g in goals:
        print(f"-- {g['name']} --")
        r = run_one(g)
        results.append(r)
        print(f"   status={r['status']}  verdict={r['verdict']}  cost=${r.get('cost_usd', 0):.4f}  wallclock={r.get('wallclock_s', 0)}s")
        if r.get("failures"):
            for f in r["failures"]:
                print(f"     ! {f}")

    summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r["status"] == "pass"),
        "failed": sum(1 for r in results if r["status"] in ("fail", "exception")),
        "results": results,
    }

    out_path = Path("sprint/v0.5/final-golden-summary.json")
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nwrote {out_path}")
    print(f"passed: {summary['passed']}/{summary['total']}")

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
