"""Skeleton for Phase 7: tools/sub_agent/index.py — parallel sub-agent fanout.

Each sub-goal runs a full `run_goal()` with isolated context. ThreadPool for
parallelism (model calls are I/O-bound, GIL is fine). Recursion blocked by
default via tool denylist. Budget pre-flight check before spawning.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any


DEFAULT_DENYLIST = ["sub_agent"]   # block recursion


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    sub_goals = inputs.get("sub_goals", [])
    if not isinstance(sub_goals, list) or not sub_goals:
        return {"error": {"code": "INVALID_INPUT", "message": "sub_goals must be a non-empty list"}}
    if any(not isinstance(s, str) or not s.strip() for s in sub_goals):
        return {"error": {"code": "INVALID_INPUT", "message": "every sub_goal must be a non-empty string"}}

    max_concurrent = int(inputs.get("max_concurrent", 4))
    max_concurrent = max(1, min(max_concurrent, 8))   # hard cap 8
    budget_usd_per_sub = float(inputs.get("budget_usd_per_sub", 0.10))
    timeout_min_per_sub = int(inputs.get("timeout_min_per_sub", 5))
    tool_allowlist = inputs.get("tool_allowlist")
    tool_denylist = list(inputs.get("tool_denylist", DEFAULT_DENYLIST))
    if "sub_agent" not in tool_denylist:
        # recursion is only allowed when explicitly NOT denied; respect that here
        pass
    max_depth = int(inputs.get("max_depth", 2))

    parent_goal_id = inputs.get("_goal_id", "adhoc")
    current_depth = int(inputs.get("_depth", 0))
    if current_depth + 1 > max_depth:
        return {"error": {"code": "MAX_DEPTH_EXCEEDED", "message": f"sub_agent recursion at depth {current_depth+1} exceeds max_depth={max_depth}"}}

    # --- budget pre-flight ---
    from agent.observability import _current_goal_cost as current_cost   # internal helper
    limit_env = float(os.environ.get("RASPUTIN_OMNITOOL_MAX_COST_USD", "0.50"))
    spent = current_cost()
    aggregate_demand = budget_usd_per_sub * len(sub_goals)
    if spent + aggregate_demand > limit_env:
        return {
            "error": {
                "code": "INSUFFICIENT_BUDGET",
                "message": (
                    f"would request {aggregate_demand:.4f} for {len(sub_goals)} subs; "
                    f"spent {spent:.4f}, limit {limit_env:.2f}"
                ),
            }
        }

    # --- spawn ---
    from agent import run_goal   # local import (avoid cycle)

    def _run_one(i: int, sub_goal: str) -> dict:
        sub_id = f"{parent_goal_id}/sub-{i+1}"
        try:
            result = run_goal(
                sub_goal,
                goal_id=sub_id,
                tool_allowlist=tool_allowlist,
                tool_denylist=tool_denylist,
                _budget_usd=budget_usd_per_sub,
                _max_wallclock_min=timeout_min_per_sub,
                _depth=current_depth + 1,
                _parent_goal_id=parent_goal_id,
            )
            verdict = getattr(result.get("review"), "verdict", None) if result.get("review") else None
            return {
                "sub_goal": sub_goal,
                "sub_agent_id": sub_id,
                "status": "ok" if verdict == "APPROVE" else "failed",
                "verdict": verdict,
                "summary": _extract_summary(result),
                "artifact_ids": list(result.get("artifacts", [])),
                "cost_usd": result.get("cost_usd", 0.0),
                "halted_for": result.get("reason") or result.get("trace", {}).get("halted_for"),
            }
        except Exception as exc:
            return {
                "sub_goal": sub_goal,
                "sub_agent_id": sub_id,
                "status": "error",
                "verdict": None,
                "summary": None,
                "artifact_ids": [],
                "cost_usd": 0.0,
                "halted_for": f"{type(exc).__name__}: {exc}",
            }

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_concurrent) as pool:
        futures = {pool.submit(_run_one, i, g): (i, g) for i, g in enumerate(sub_goals)}
        for fut in futures:
            try:
                res = fut.result(timeout=timeout_min_per_sub * 60 + 30)
            except FuturesTimeout:
                i, g = futures[fut]
                res = {
                    "sub_goal": g,
                    "sub_agent_id": f"{parent_goal_id}/sub-{i+1}",
                    "status": "timeout",
                    "verdict": None,
                    "summary": None,
                    "artifact_ids": [],
                    "cost_usd": 0.0,
                    "halted_for": "WALLCLOCK",
                }
            results.append(res)

    aggregate_cost = sum(r["cost_usd"] for r in results)
    successful = sum(1 for r in results if r["status"] == "ok")
    failed = len(results) - successful

    # propagate cost to parent
    try:
        from agent.observability import _add_cost
        _add_cost(aggregate_cost)
    except Exception:
        pass

    return {
        "result": {
            "results": results,
            "aggregate_cost_usd": aggregate_cost,
            "successful_count": successful,
            "failed_count": failed,
        }
    }


def _extract_summary(result: dict) -> str | None:
    trace = result.get("trace")
    if trace is None:
        return None
    final = getattr(trace, "final_answer", None)
    if final:
        return final
    review = result.get("review")
    if review is not None:
        return getattr(review, "notes", None)
    return None


if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(run(json.loads(sys.stdin.read()))))
