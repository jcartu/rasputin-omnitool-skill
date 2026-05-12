"""Agent loop — planner → executor → reviewer with one-shot revise."""
from __future__ import annotations

from typing import Any

from agent.planner import Plan as Plan, plan
from agent.executor import ExecutionTrace as ExecutionTrace
from agent.executor_router import execute
from agent.reviewer import Review as Review, review
from agent.tool_registry import load_tools, load_tool_metadata
from agent.observability import goal_trace, CostCeilingExceeded


def run_goal(goal: str, goal_id: str | None = None) -> dict[str, Any]:
    """Run the full agent loop: plan → execute → review (with one revise attempt).

    Returns a dict with plan, trace, artifacts, and review.
    Halts cleanly with halted=True if cost ceiling is exceeded.
    """
    with goal_trace(goal, goal_id):
        try:
            tools_meta = load_tool_metadata()
            plan_obj = plan(goal, tools_meta)
            tools = load_tools()
            trace = execute(plan_obj, tools)
            artifacts = list(trace.artifacts)
            rev = review(trace, artifacts)

            if rev.verdict == "REVISE":
                # One re-plan attempt
                revised_goal = goal + f"\n\nReviewer findings to address:\n{rev.notes}"
                plan_obj_v2 = plan(revised_goal, tools_meta)
                trace_v2 = execute(plan_obj_v2, tools)
                artifacts_v2 = list(trace_v2.artifacts)
                rev_v2 = review(trace_v2, artifacts_v2)
                return {
                    "goal_id": goal_id,
                    "plan": plan_obj_v2,
                    "trace": trace_v2,
                    "artifacts": artifacts_v2,
                    "review": rev_v2,
                    "revised": True,
                }

            return {
                "goal_id": goal_id,
                "plan": plan_obj,
                "trace": trace,
                "artifacts": artifacts,
                "review": rev,
                "revised": False,
            }
        except CostCeilingExceeded as exc:
            return {
                "goal_id": goal_id,
                "halted": True,
                "reason": "cost_ceiling_exceeded",
                "details": {"spent": exc.current, "limit": exc.limit},
                "results": [],
            }


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
