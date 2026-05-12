"""Tests for cost telemetry and ceiling enforcement."""
from __future__ import annotations

from unittest.mock import Mock

import pytest

from agent.observability import (
    CostCeilingExceeded,
    estimate_cost_usd,
    check_cost_ceiling,
    record_call_cost,
    _current_goal_cost,
    _reset_cost,
    extract_usage,
)


@pytest.fixture(autouse=True)
def _reset():
    _reset_cost()
    yield
    _reset_cost()


def test_opus_cost_calculation():
    # 1M input + 0.5M output Opus call
    cost = estimate_cost_usd("claude-opus-4-7", 1_000_000, 500_000)
    assert abs(cost - (15.0 + 37.5)) < 0.01


def test_local_27b_cost_is_zero():
    cost = estimate_cost_usd("qwen3-27b-instruct", 100_000, 100_000)
    assert cost == 0.0


def test_unknown_model_cost_is_zero():
    cost = estimate_cost_usd("some-unknown-model", 1000, 1000)
    assert cost == 0.0


def test_cost_accumulates_across_calls():
    record_call_cost("claude-opus-4-7", 10_000, 5_000)
    record_call_cost("claude-opus-4-7", 10_000, 5_000)
    assert _current_goal_cost() > 0
    # Two identical calls should be 2x one call
    _reset_cost()
    record_call_cost("claude-opus-4-7", 10_000, 5_000)
    one_call = _current_goal_cost()
    record_call_cost("claude-opus-4-7", 10_000, 5_000)
    assert abs(_current_goal_cost() - 2 * one_call) < 0.001


def test_ceiling_enforced(monkeypatch):
    monkeypatch.setenv("RASPUTIN_OMNITOOL_MAX_COST_USD", "0.10")
    # First call: small, under ceiling
    check_cost_ceiling("claude-opus-4-7", 1000, 100)
    record_call_cost("claude-opus-4-7", 1000, 100)
    # Big call would push over
    with pytest.raises(CostCeilingExceeded) as exc_info:
        check_cost_ceiling("claude-opus-4-7", 100_000, 100_000)
    assert exc_info.value.current > 0
    assert exc_info.value.limit == 0.10


def test_extract_usage_anthropic_shape():
    resp = Mock()
    resp.usage = Mock()
    resp.usage.input_tokens = 1234
    resp.usage.output_tokens = 567
    # ensure prompt_tokens path doesn't accidentally match first
    del resp.usage.prompt_tokens  # type: ignore
    p, c = extract_usage(resp)
    assert (p, c) == (1234, 567)


def test_extract_usage_openai_shape():
    resp = Mock()
    resp.usage = Mock(spec=["prompt_tokens", "completion_tokens"])
    resp.usage.prompt_tokens = 100
    resp.usage.completion_tokens = 50
    p, c = extract_usage(resp)
    assert (p, c) == (100, 50)


def test_extract_usage_dict_shape():
    resp = Mock()
    resp.usage = {"prompt_tokens": 7, "completion_tokens": 3}
    p, c = extract_usage(resp)
    assert (p, c) == (7, 3)


def test_extract_usage_missing_returns_zero():
    resp = Mock(spec=[])  # no usage attribute
    p, c = extract_usage(resp)
    assert (p, c) == (0, 0)
