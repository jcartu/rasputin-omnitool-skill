"""Parallel sub-agent fan-out tool."""
from __future__ import annotations

import os
from concurrent.futures import ALL_COMPLETED, ThreadPoolExecutor, wait
from typing import Any


DEFAULT_DENYLIST = ["sub_agent"]


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    sub_goals = inputs.get("sub_goals", [])
    if not isinstance(sub_goals, list) or not sub_goals:
        return {"error": {"code": "INVALID_INPUT", "message": "sub_goals must be a non-empty list"}}
    if any(not isinstance(item, str) or not item.strip() for item in sub_goals):
        return {"error": {"code": "INVALID_INPUT", "message": "every sub_goal must be a non-empty string"}}

    max_concurrent = max(1, min(int(inputs.get("max_concurrent", 4)), 8))
    budget_usd_per_sub = float(inputs.get("budget_usd_per_sub", 0.10))
    timeout_min_per_sub = float(inputs.get("timeout_min_per_sub", 5))
    max_depth = int(inputs.get("max_depth", 2))
    tool_allowlist = inputs.get("tool_allowlist")
    tool_denylist = list(inputs.get("tool_denylist", DEFAULT_DENYLIST))
    parent_goal_id = str(inputs.get("_goal_id") or inputs.get("goal_id") or "adhoc")
    current_depth = int(inputs.get("_depth", 0))

    if current_depth + 1 > max_depth:
        return {
            "error": {
                "code": "MAX_DEPTH_EXCEEDED",
                "message": f"sub_agent recursion at depth {current_depth + 1} exceeds max_depth={max_depth}",
            }
        }

    budget_error = _budget_preflight(budget_usd_per_sub, len(sub_goals))
    if budget_error is not None:
        return budget_error

    from agent import run_goal

    def _run_one(index: int, sub_goal: str) -> dict[str, Any]:
        sub_id = f"{parent_goal_id}/sub-{index + 1}"
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
            artifact_ids = [str(item) for item in result.get("artifacts", [])]
            _tag_artifacts_for_parent(artifact_ids, parent_goal_id, sub_id)
            verdict = _verdict(result)
            halted_for = result.get("reason") or _trace_halted_for(result.get("trace"))
            status = "ok" if verdict == "APPROVE" and not result.get("halted") else "failed"
            return {
                "sub_goal": sub_goal,
                "sub_agent_id": sub_id,
                "status": status,
                "verdict": verdict,
                "summary": _extract_summary(result),
                "artifact_ids": artifact_ids,
                "cost_usd": float(result.get("cost_usd", 0.0) or 0.0),
                "halted_for": halted_for,
            }
        except Exception as exc:  # pragma: no cover - defensive serialization path
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

    timeout_s = max(0.0, timeout_min_per_sub * 60.0)
    results_by_index: dict[int, dict[str, Any]] = {}
    pool = ThreadPoolExecutor(max_workers=max_concurrent)
    try:
        future_map = {pool.submit(_run_one, index, goal): (index, goal) for index, goal in enumerate(sub_goals)}
        done, pending = wait(future_map, timeout=timeout_s, return_when=ALL_COMPLETED)
        for future in done:
            index, _goal = future_map[future]
            results_by_index[index] = future.result()
        for future in pending:
            index, goal = future_map[future]
            future.cancel()
            results_by_index[index] = {
                "sub_goal": goal,
                "sub_agent_id": f"{parent_goal_id}/sub-{index + 1}",
                "status": "timeout",
                "verdict": None,
                "summary": None,
                "artifact_ids": [],
                "cost_usd": 0.0,
                "halted_for": "WALLCLOCK",
            }
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    results = [results_by_index[index] for index in range(len(sub_goals))]
    aggregate_cost = sum(float(item["cost_usd"]) for item in results)
    successful = sum(1 for item in results if item["status"] == "ok")

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
            "failed_count": len(results) - successful,
        }
    }


def _budget_preflight(budget_usd_per_sub: float, sub_count: int) -> dict[str, Any] | None:
    from agent.observability import _current_goal_cost as current_cost

    limit = float(os.environ.get("RASPUTIN_OMNITOOL_MAX_COST_USD", "0.50"))
    spent = current_cost()
    aggregate_demand = budget_usd_per_sub * sub_count
    if spent + aggregate_demand <= limit:
        return None
    return {
        "error": {
            "code": "INSUFFICIENT_BUDGET",
            "message": (
                f"would request {aggregate_demand:.4f} for {sub_count} subs; "
                f"spent {spent:.4f}, limit {limit:.2f}"
            ),
        }
    }


def _extract_summary(result: dict[str, Any]) -> str | None:
    trace = result.get("trace")
    final_answer = getattr(trace, "final_answer", None)
    if final_answer:
        return final_answer
    if isinstance(trace, dict) and trace.get("final_answer"):
        return str(trace["final_answer"])
    review = result.get("review")
    notes = getattr(review, "notes", None)
    if notes:
        return notes
    if isinstance(review, dict) and review.get("notes"):
        return str(review["notes"])
    return None


def _trace_halted_for(trace: Any) -> str | None:
    if isinstance(trace, dict):
        return trace.get("halted_for")
    return getattr(trace, "halted_for", None)


def _verdict(result: dict[str, Any]) -> str | None:
    review = result.get("review")
    if isinstance(review, dict):
        verdict = review.get("verdict")
    else:
        verdict = getattr(review, "verdict", None)
    return str(verdict) if verdict is not None else None


def _tag_artifacts_for_parent(artifact_ids: list[str], parent_goal_id: str, sub_agent_id: str) -> None:
    if not artifact_ids:
        return
    try:
        from agent.artifact_registry import get_registry

        registry = get_registry()
        with registry._lock, registry._conn:  # noqa: SLF001 - no public retag API yet
            registry._conn.executemany(  # noqa: SLF001
                "UPDATE artifact SET goal_id = ?, sub_agent_id = ? WHERE id = ?",
                [(parent_goal_id, sub_agent_id, artifact_id) for artifact_id in artifact_ids],
            )
    except Exception:
        pass


if __name__ == "__main__":
    import json
    import sys

    print(json.dumps(run(json.loads(sys.stdin.read()))))
