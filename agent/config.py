"""Runtime configuration for become-manus-skill."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Environment-backed config defaults."""

    planner_model: str = os.getenv("BECOME_MANUS_PLANNER_MODEL", "Qwen3.5-27B")
    executor_model: str = os.getenv("BECOME_MANUS_EXECUTOR_MODEL", "Qwen3.5-27B")
    reviewer_model: str = os.getenv("BECOME_MANUS_REVIEWER_MODEL", "claude-opus-4-7")
    max_goal_cost_usd: float = float(os.getenv("BECOME_MANUS_MAX_GOAL_COST_USD", "0.10"))
    langfuse_public_key: str | None = os.getenv("LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str | None = os.getenv("LANGFUSE_SECRET_KEY")
    langfuse_host: str = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
    outputs_dir: str = os.getenv("BECOME_MANUS_OUTPUTS_DIR", "outputs")
    sandbox_url: str = os.getenv("BECOME_MANUS_SANDBOX_URL", "http://localhost:8080")


CONFIG = Config()
