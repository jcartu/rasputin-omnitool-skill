"""Checkpoint demo: simulate kill-and-resume flow.

Demonstrates: write checkpoints, simulate kill, verify resume loads state.
Usage: python scripts/checkpoint_demo.py
"""
from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

from agent.checkpoint import (
    CheckpointManager,
    GoalCheckpoint,
    get_checkpoint_manager,
)


def main():
    tmp = tempfile.mkdtemp(prefix="ckpt_demo_")
    os.environ["RASPUTIN_OMNITOOL_CHECKPOINT_ROOT"] = str(Path(tmp) / "checkpoints")

    goal_id = "demo-goal-1"
    goal_text = "Search for 'OpenAI' and summarize"
    ckpt_root = Path(tmp) / "checkpoints"

    print(f"Checkpoint root: {ckpt_root}")
    print(f"Goal ID: {goal_id}")

    mgr = CheckpointManager(root=ckpt_root, keep=5)

    # Phase 1: simulate partial execution (3 steps, then "kill")
    print("\n=== Phase 1: Simulating partial execution ===")

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": goal_text},
    ]
    trace_steps = []

    for step in range(3):
        # Simulate a tool call
        messages.append({
            "role": "assistant",
            "content": f"Step {step + 1}: searching...",
            "tool_calls": [{"id": f"call_{step}", "type": "function", "function": {"name": "crawl4ai", "arguments": '{"url": "https://example.com"}'}}],
        })
        messages.append({
            "role": "tool",
            "tool_call_id": f"call_{step}",
            "content": f"Step {step + 1} result: found relevant information.",
        })
        trace_steps.append({
            "step": step,
            "kind": "tool_call",
            "tool": "crawl4ai",
            "status": "ok",
        })

        # Write checkpoint after each step (like react_executor does)
        cp = GoalCheckpoint(
            goal_id=goal_id,
            sprint_id=None,
            goal_text=goal_text,
            step_count=step + 1,
            cost_usd=0.02 * (step + 1),
            messages=list(messages),
            trace_steps=list(trace_steps),
            artifact_ids=[],
            sandbox_session_ids=[],
            browser_session_ids=[],
            created_at=time.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        )
        path = mgr.write(cp)
        print(f"  Step {step + 1}: checkpoint written to {path.name}")

    # Simulate kill
    print("\n=== Simulating process kill (SIGKILL) ===")
    print("  Process killed. Checkpoints on disk survive.")

    # Show checkpoint state
    ckpt_dir = ckpt_root / goal_id
    print("\nCheckpoint directory contents:")
    for f in sorted(ckpt_dir.iterdir()):
        print(f"  {f.name}")

    latest = mgr.load(goal_id)
    print(f"\nLatest checkpoint: step {latest.step_count}, {len(latest.messages)} messages")

    # Phase 2: resume
    print("\n=== Phase 2: Resuming from checkpoint ===")

    from agent import resume_goal

    with resume_goal_mock(goal_id, mgr):
        result = resume_goal(goal_id, allow_session_loss=True)

    print(f"Resume result: goal_id={result.get('goal_id')}")
    print("  (In production, this would re-run the goal from the checkpoint)")

    # Show final state
    print("\nFinal checkpoint directory:")
    for f in sorted(ckpt_dir.iterdir()):
        print(f"  {f.name}")

    print("\nDemo complete. Checkpoints survived simulated kill-and-resume.")


class resume_goal_mock:
    """Context manager that patches resume_goal to return a mock result."""
    def __init__(self, goal_id, mgr):
        self.goal_id = goal_id
        self.mgr = mgr

    def __enter__(self):
        from unittest.mock import patch

        self._patch1 = patch.object(get_checkpoint_manager(), "latest", return_value=self.mgr.load(self.goal_id))
        self._patch2 = patch("agent.run_goal")
        self._patch2.start().return_value = {
            "goal_id": self.goal_id,
            "halted": False,
            "review": type("Review", (), {"verdict": "APPROVE"})(),
            "artifacts": ["outputs/report.md"],
        }
        return self

    def __exit__(self, *exc):
        self._patch1.stop()
        self._patch2.stop()


if __name__ == "__main__":
    main()
