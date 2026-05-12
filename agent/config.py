"""Runtime configuration for rasputin-omnitool-skill."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Environment-backed config defaults."""

    planner_model: str = os.getenv("RASPUTIN_OMNITOOL_PLANNER_MODEL", "gpt-oss-120b")
    executor_mode: str = os.getenv("RASPUTIN_OMNITOOL_EXECUTOR_MODE", "react")
    executor_model: str = os.getenv("RASPUTIN_OMNITOOL_EXECUTOR_MODEL", "gpt-oss-120b")
    executor_endpoint: str = os.getenv("RASPUTIN_OMNITOOL_EXECUTOR_ENDPOINT", "http://localhost:11434/v1")
    reviewer_model: str = os.getenv("RASPUTIN_OMNITOOL_REVIEWER_MODEL", "claude-opus-4-7")
    max_goal_cost_usd: float = float(os.getenv("RASPUTIN_OMNITOOL_MAX_GOAL_COST_USD", "0.10"))
    max_steps_per_goal: int = int(os.getenv("RASPUTIN_OMNITOOL_MAX_STEPS", "30"))
    max_tool_failure_rate: float = float(os.getenv("RASPUTIN_OMNITOOL_MAX_TOOL_FAILURE_RATE", "0.30"))
    max_wallclock_per_goal_min: int = int(os.getenv("RASPUTIN_OMNITOOL_MAX_WALLCLOCK_MIN", "20"))
    soft_cap_tokens: int = int(os.getenv("RASPUTIN_OMNITOOL_SOFT_CAP_TOKENS", "18000"))
    langfuse_public_key: str | None = os.getenv("LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str | None = os.getenv("LANGFUSE_SECRET_KEY")
    langfuse_host: str = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
    outputs_dir: str = os.getenv("RASPUTIN_OMNITOOL_OUTPUTS_DIR", "outputs")
    sandbox_url: str = os.getenv("RASPUTIN_OMNITOOL_SANDBOX_URL", "http://localhost:8080")
    sandbox_session_ttl_min: int = int(os.getenv("RASPUTIN_OMNITOOL_SANDBOX_SESSION_TTL_MIN", "60"))
    sandbox_max_sessions: int = int(os.getenv("RASPUTIN_OMNITOOL_SANDBOX_MAX_SESSIONS", "10"))
    session_root: str = os.getenv("RASPUTIN_OMNITOOL_SESSION_ROOT", "~/.rasputin/sessions/sandbox")
    browser_session_root: str = os.getenv("RASPUTIN_OMNITOOL_BROWSER_SESSION_ROOT", "~/.rasputin/sessions/browser")
    browser_session_ttl_min: int = int(os.getenv("RASPUTIN_OMNITOOL_BROWSER_SESSION_TTL_MIN", "60"))
    browser_max_sessions: int = int(os.getenv("RASPUTIN_OMNITOOL_BROWSER_MAX_SESSIONS", "10"))

CONFIG = Config()
