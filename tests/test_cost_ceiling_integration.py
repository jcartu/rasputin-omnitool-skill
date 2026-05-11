"""Integration: a goal that would blow past the ceiling halts cleanly."""
from __future__ import annotations

import os
from unittest.mock import patch, Mock

import pytest

from agent import run_goal


def test_low_ceiling_halts_goal_cleanly(monkeypatch):
    monkeypatch.setenv("RASPUTIN_OMNITOOL_MAX_COST_USD", "0.0001")
    # Use Opus as planner model so cost estimate triggers ceiling before LLM call
    monkeypatch.setattr("agent.planner.CONFIG", type('C', (), {
        "planner_model": "claude-opus-4-7",
        "executor_endpoint": "http://localhost:11434/v1",
    })()), 
    # Mock the planner LLM to return a response with huge token counts
    # so the cost ceiling is hit immediately
    fake_response = Mock(spec=["choices", "usage"])
    fake_response.choices = [Mock(message=Mock(content="{}"))]
    fake_response.usage = Mock(spec=["prompt_tokens", "completion_tokens"])
    fake_response.usage.prompt_tokens = 100_000
    fake_response.usage.completion_tokens = 50_000

    with patch("agent.planner.OpenAI") as mock_openai_cls:
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = fake_response
        mock_openai_cls.return_value = mock_client

        result = run_goal("test goal that should hit ceiling")

    assert result.get("halted") is True
    assert result.get("reason") == "cost_ceiling_exceeded"
    assert result.get("details", {}).get("spent", -1) >= 0
    assert result.get("details", {}).get("limit", -1) == 0.0001
