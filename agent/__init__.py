"""Agent loop — planner → executor → reviewer with one-shot revise."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agent.planner import Plan as Plan, plan
from agent.executor import ExecutionTrace as ExecutionTrace
from agent.event_stream import StreamEvent, get_event_bus
from agent.executor_router import execute
from agent.reviewer import Review as Review, review
from agent.tool_registry import load_tools, load_tool_metadata
from agent.observability import CostCeilingExceeded, _current_goal_cost, goal_trace


def run_goal(
    goal: str,
    goal_id: str | None = None,
    tool_allowlist: list[str] | None = None,
    tool_denylist: list[str] | None = None,
    _budget_usd: float | None = None,
    _max_wallclock_min: int | float | None = None,
    _depth: int = 0,
    _parent_goal_id: str | None = None,
    on_event: Callable[[StreamEvent], None] | None = None,
) -> dict[str, Any]:
    """Run the full agent loop: plan → execute → review (with one revise attempt).

    Returns a dict with plan, trace, artifacts, and review.
    Halts cleanly with halted=True if cost ceiling is exceeded.
    """
    event_bus = get_event_bus()
    sub_id = event_bus.subscribe_sync(on_event) if on_event else None
    effective_goal_id = goal_id or "ad-hoc"
    event_bus.emit_typed("goal.started", effective_goal_id, goal_text=goal)
    with goal_trace(goal, goal_id):
        try:
            tools_meta = load_tool_metadata()
            plan_obj = plan(goal, tools_meta)
            tools = load_tools(allowlist=tool_allowlist, denylist=tool_denylist)
            trace = execute(
                plan_obj,
                tools,
                context={
                    "goal_id": effective_goal_id,
                    "_depth": _depth,
                    "_parent_goal_id": _parent_goal_id,
                },
                budget_usd=_budget_usd,
                max_wallclock_min=_max_wallclock_min,
            )
            artifacts = list(trace.artifacts)
            rev = review(trace, artifacts)

            if rev.verdict == "REVISE":
                # One re-plan attempt
                revised_goal = goal + f"\n\nReviewer findings to address:\n{rev.notes}"
                plan_obj_v2 = plan(revised_goal, tools_meta)
                trace_v2 = execute(
                    plan_obj_v2,
                    tools,
                    context={
                        "goal_id": effective_goal_id,
                        "_depth": _depth,
                        "_parent_goal_id": _parent_goal_id,
                    },
                    budget_usd=_budget_usd,
                    max_wallclock_min=_max_wallclock_min,
                )
                artifacts_v2 = list(trace_v2.artifacts)
                rev_v2 = review(trace_v2, artifacts_v2)
                result = {
                    "goal_id": effective_goal_id,
                    "plan": plan_obj_v2,
                    "trace": trace_v2,
                    "artifacts": artifacts_v2,
                    "review": rev_v2,
                    "revised": True,
                    "cost_usd": _current_goal_cost(),
                }
                if trace_v2.halted_for:
                    event_bus.emit_typed(
                        "goal.halted",
                        effective_goal_id,
                        reason=trace_v2.halted_for,
                        last_checkpoint=None,
                    )
                else:
                    event_bus.emit_typed(
                        "goal.completed",
                        effective_goal_id,
                        verdict=rev_v2.verdict,
                        artifacts=artifacts_v2,
                        cost_usd=result["cost_usd"],
                        halted_for=None,
                    )
                return result

            result = {
                "goal_id": effective_goal_id,
                "plan": plan_obj,
                "trace": trace,
                "artifacts": artifacts,
                "review": rev,
                "revised": False,
                "cost_usd": _current_goal_cost(),
            }
            if trace.halted_for:
                event_bus.emit_typed(
                    "goal.halted",
                    effective_goal_id,
                    reason=trace.halted_for,
                    last_checkpoint=None,
                )
            else:
                event_bus.emit_typed(
                    "goal.completed",
                    effective_goal_id,
                    verdict=rev.verdict,
                    artifacts=artifacts,
                    cost_usd=result["cost_usd"],
                    halted_for=None,
                )
            return result
        except CostCeilingExceeded as exc:
            event_bus.emit_typed(
                "goal.halted",
                effective_goal_id,
                reason="cost_ceiling_exceeded",
                last_checkpoint=None,
            )
            return {
                "goal_id": goal_id,
                "halted": True,
                "reason": "cost_ceiling_exceeded",
                "details": {"spent": exc.current, "limit": exc.limit},
                "results": [],
            }
        finally:
            if sub_id is not None:
                event_bus.unsubscribe(sub_id)


def resume_goal(goal_id: str, allow_session_loss: bool = False) -> dict[str, Any]:
    """Resume a goal from its latest checkpoint."""
    from agent.checkpoint import get_checkpoint_manager

    mgr = get_checkpoint_manager()
    cp = mgr.latest(goal_id)
    if cp is None:
        return {
            "goal_id": goal_id,
            "halted": True,
            "reason": "NO_CHECKPOINT",
            "details": {"message": f"No checkpoint found for goal {goal_id}"},
        }

    # Verify sessions are alive
    dead_sessions: list[str] = []
    if not allow_session_loss:
        from agent.session_manager import get_sandbox_session_manager
        sandbox_mgr = get_sandbox_session_manager()
        for sid in cp.sandbox_session_ids:
            if not sandbox_mgr.is_alive(sid):
                dead_sessions.append(sid)
        if dead_sessions:
            return {
                "goal_id": goal_id,
                "halted": True,
                "reason": "SESSIONS_EXPIRED",
                "details": {"dead_sessions": dead_sessions},
            }

    # Re-run with checkpoint context
    goal_text = cp.goal_text
    return run_goal(goal_text, goal_id=goal_id)
