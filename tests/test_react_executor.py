"""Unit tests for the ReAct executor — mocked LLM, no real API calls."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock, patch


from agent.planner import Plan, PlanTask
from agent.react_executor import (
    _compact_if_oversize,
    _estimate_tokens,
    _format_user_message,
    _hash_args,
    _plan_to_dict,
    _preview,
    _serialize_observation,
    react_execute,
)


def _mock_response(content: str | None = None, tool_calls: list[dict] | None = None, finish_reason: str = "stop"):
    """Build a mock OpenAI chat completion response."""
    msg = SimpleNamespace(
        content=content,
        tool_calls=[],
    )
    if tool_calls:
        msg.tool_calls = [
            SimpleNamespace(id=f"call_{i}", function=SimpleNamespace(name=tc["name"], arguments=json.dumps(tc["args"])))
            for i, tc in enumerate(tool_calls)
        ]
    choice = SimpleNamespace(message=msg, finish_reason=finish_reason)
    usage = SimpleNamespace(prompt_tokens=100, completion_tokens=50)
    return SimpleNamespace(choices=[choice], usage=usage)


def _mock_client(responses: list):
    """Return a mock OpenAI client that yields responses in order."""
    client = Mock()
    client.chat.completions.create = Mock(side_effect=responses)
    return client


def _make_plan(tasks: list[dict] | None = None) -> Plan:
    tasks = tasks or []
    return Plan(
        goal="test goal",
        tasks=[PlanTask(**t) for t in tasks],
        success_criteria=["done"],
    )


# ── 1. Single tool, one call ──────────────────────────────────────────────


def test_single_tool_one_call():
    """Mock LLM emits one tool_call then a stop. Trace has one step, final answer present."""
    responses = [
        _mock_response(tool_calls=[{"name": "web_search", "args": {"query": "hello"}}], finish_reason="tool_calls"),
        _mock_response(content="The answer is 42.", finish_reason="stop"),
    ]
    client = _mock_client(responses)

    tools = {"web_search": lambda args: {"result": {"results": [{"title": "Hello", "url": "http://example.com"}]}}}
    metadata = [{"name": "web_search", "description": "Search", "tags": ["web"], "available": True, "inputs": {}, "outputs": {}, "errors": []}]

    with patch("agent.react_executor.OpenAI", return_value=client):
        with patch("agent.react_executor.check_cost_ceiling"):
            trace = react_execute("Search for hello", tools, metadata, plan_hint=None, max_steps=10)

    assert trace.halted_for is None
    assert trace.final_answer == "The answer is 42."
    assert len(trace.steps) == 2  # tool_call + final_answer
    assert trace.steps[0]["kind"] == "tool_call"
    assert trace.steps[0]["tool"] == "web_search"
    assert trace.steps[1]["kind"] == "final_answer"


# ── 2. Two tools, sequential ──────────────────────────────────────────────


def test_two_tools_sequential():
    """Mock LLM emits crawl, observes, then deliverables, then stop. Trace has two steps."""
    responses = [
        _mock_response(tool_calls=[{"name": "crawl4ai", "args": {"url": "http://example.com"}}], finish_reason="tool_calls"),
        _mock_response(tool_calls=[{"name": "deliverables", "args": {"format": "markdown"}}], finish_reason="tool_calls"),
        _mock_response(content="Done.", finish_reason="stop"),
    ]
    client = _mock_client(responses)

    tools = {
        "crawl4ai": lambda args: {"result": {"markdown": "# Hello", "url": "http://example.com"}},
        "deliverables": lambda args: {"result": {"path": "outputs/report.md"}},
    }
    metadata = [
        {"name": "crawl4ai", "description": "Crawl", "tags": ["web"], "available": True, "inputs": {}, "outputs": {}, "errors": []},
        {"name": "deliverables", "description": "Deliver", "tags": ["output"], "available": True, "inputs": {}, "outputs": {}, "errors": []},
    ]

    with patch("agent.react_executor.OpenAI", return_value=client):
        with patch("agent.react_executor.check_cost_ceiling"):
            trace = react_execute("Crawl and deliver", tools, metadata, plan_hint=None, max_steps=10)

    assert trace.halted_for is None
    assert trace.final_answer == "Done."
    assert len(trace.steps) == 3  # 2 tool_calls + 1 final_answer
    assert trace.steps[0]["tool"] == "crawl4ai"
    assert trace.steps[1]["tool"] == "deliverables"
    assert "outputs/report.md" in trace.artifacts


# ── 3. Tool error recovered ───────────────────────────────────────────────


def test_tool_error_recovered():
    """Mock LLM emits broken call, observes error, picks different tool, succeeds."""
    responses = [
        _mock_response(tool_calls=[{"name": "web_search", "args": {"query": "bad"}}], finish_reason="tool_calls"),
        _mock_response(tool_calls=[{"name": "crawl4ai", "args": {"url": "http://example.com"}}], finish_reason="tool_calls"),
        _mock_response(content="Recovered.", finish_reason="stop"),
    ]
    client = _mock_client(responses)

    def flaky_search(args):
        raise RuntimeError("search failed")

    tools = {
        "web_search": flaky_search,
        "crawl4ai": lambda args: {"result": {"markdown": "ok"}},
    }
    metadata = [
        {"name": "web_search", "description": "Search", "tags": ["web"], "available": True, "inputs": {}, "outputs": {}, "errors": []},
        {"name": "crawl4ai", "description": "Crawl", "tags": ["web"], "available": True, "inputs": {}, "outputs": {}, "errors": []},
    ]

    with patch("agent.react_executor.OpenAI", return_value=client):
        with patch("agent.react_executor.check_cost_ceiling"):
            trace = react_execute("Search then crawl", tools, metadata, plan_hint=None, max_steps=10)

    assert trace.halted_for is None
    assert trace.final_answer == "Recovered."
    assert trace.steps[0]["kind"] == "tool_call"
    assert trace.steps[0]["status"] == "error"
    assert trace.steps[1]["tool"] == "crawl4ai"
    assert trace.steps[1]["status"] == "ok"


# ── 4. Dedup triggers ─────────────────────────────────────────────────────


def test_dedup_triggers():
    """Mock LLM emits same (name, args) three times; third gets DUPLICATE_TOOL_CALL."""
    responses = [
        _mock_response(tool_calls=[{"name": "web_search", "args": {"query": "same"}}], finish_reason="tool_calls"),
        _mock_response(tool_calls=[{"name": "web_search", "args": {"query": "same"}}], finish_reason="tool_calls"),
        _mock_response(tool_calls=[{"name": "web_search", "args": {"query": "same"}}], finish_reason="tool_calls"),
        _mock_response(content="Gave up.", finish_reason="stop"),
    ]
    client = _mock_client(responses)

    tools = {"web_search": lambda args: {"error": {"code": "RATE_LIMIT"}}}
    metadata = [
        {"name": "web_search", "description": "Search", "tags": ["web"], "available": True, "inputs": {}, "outputs": {}, "errors": []},
    ]

    with patch("agent.react_executor.OpenAI", return_value=client):
        with patch("agent.react_executor.check_cost_ceiling"):
            trace = react_execute("Search same thing", tools, metadata, plan_hint=None, max_steps=10)

    # Third call should have DUPLICATE_TOOL_CALL in observation_preview
    third_step = trace.steps[2]
    assert third_step["kind"] == "tool_call"
    assert "DUPLICATE_TOOL_CALL" in third_step["observation_preview"]


# ── 5. Budget exceeded ────────────────────────────────────────────────────


def test_budget_exceeded():
    """Set budget_usd=0.001; loop halts with BUDGET after the first paid call."""
    responses = [
        _mock_response(tool_calls=[{"name": "web_search", "args": {"query": "x"}}], finish_reason="tool_calls"),
    ]
    client = _mock_client(responses)

    tools = {"web_search": lambda args: {"result": {"results": []}}}
    metadata = [
        {"name": "web_search", "description": "Search", "tags": ["web"], "available": True, "inputs": {}, "outputs": {}, "errors": []},
    ]

    with patch("agent.react_executor.OpenAI", return_value=client):
        with patch("agent.react_executor.check_cost_ceiling"):
            with patch("agent.react_executor.record_call_cost", return_value=1.0):
                trace = react_execute("expensive goal", tools, metadata, plan_hint=None, max_steps=10, budget_usd=0.001)

    assert trace.halted_for == "BUDGET"


# ── 6. Max steps exceeded ─────────────────────────────────────────────────


def test_max_steps_exceeded():
    """Set max_steps=2; loop halts with MAX_STEPS."""
    responses = [
        _mock_response(tool_calls=[{"name": "web_search", "args": {"query": "a"}}], finish_reason="tool_calls"),
        _mock_response(tool_calls=[{"name": "web_search", "args": {"query": "b"}}], finish_reason="tool_calls"),
    ]
    client = _mock_client(responses)

    tools = {"web_search": lambda args: {"result": {"results": []}}}
    metadata = [
        {"name": "web_search", "description": "Search", "tags": ["web"], "available": True, "inputs": {}, "outputs": {}, "errors": []},
    ]

    with patch("agent.react_executor.OpenAI", return_value=client):
        with patch("agent.react_executor.check_cost_ceiling"):
            trace = react_execute("loop goal", tools, metadata, plan_hint=None, max_steps=2)

    assert trace.halted_for == "MAX_STEPS"


# ── 7. Wall-clock exceeded ────────────────────────────────────────────────


def test_wallclock_exceeded():
    """Mock elapsed time > max_wallclock_min; halts with WALLCLOCK."""
    responses = [
        _mock_response(tool_calls=[{"name": "web_search", "args": {"query": "x"}}], finish_reason="tool_calls"),
    ]
    client = _mock_client(responses)

    tools = {"web_search": lambda args: {"result": {"results": []}}}
    metadata = [
        {"name": "web_search", "description": "Search", "tags": ["web"], "available": True, "inputs": {}, "outputs": {}, "errors": []},
    ]

    with patch("agent.react_executor.OpenAI", return_value=client):
        with patch("agent.react_executor.check_cost_ceiling"):
            with patch("agent.react_executor.time.time") as mock_time:
                mock_time.side_effect = [0.0, 0.0, 3601.0]  # start, model call, then >20 min
                trace = react_execute("slow goal", tools, metadata, plan_hint=None, max_steps=10, max_wallclock_min=20)

    assert trace.halted_for == "WALLCLOCK"


# ── 8. Unknown tool ───────────────────────────────────────────────────────


def test_unknown_tool():
    """Mock LLM calls bogus_tool; gets UNKNOWN_TOOL observation, then resolves."""
    responses = [
        _mock_response(tool_calls=[{"name": "bogus_tool", "args": {}}], finish_reason="tool_calls"),
        _mock_response(content="Adapted.", finish_reason="stop"),
    ]
    client = _mock_client(responses)

    tools = {"web_search": lambda args: {"result": {"results": []}}}
    metadata = [
        {"name": "web_search", "description": "Search", "tags": ["web"], "available": True, "inputs": {}, "outputs": {}, "errors": []},
    ]

    with patch("agent.react_executor.OpenAI", return_value=client):
        with patch("agent.react_executor.check_cost_ceiling"):
            trace = react_execute("use bogus tool", tools, metadata, plan_hint=None, max_steps=10)

    assert trace.steps[0]["kind"] == "tool_call"
    assert trace.steps[0]["status"] == "error"
    assert "UNKNOWN_TOOL" in trace.steps[0]["observation_preview"]
    assert trace.final_answer == "Adapted."


# ── 9. Empty plan_hint works ──────────────────────────────────────────────


def test_empty_plan_hint():
    """Pass plan_hint=None; executor runs from goal alone."""
    responses = [
        _mock_response(content="No plan needed.", finish_reason="stop"),
    ]
    client = _mock_client(responses)

    tools = {"web_search": lambda args: {"result": {"results": []}}}
    metadata = [
        {"name": "web_search", "description": "Search", "tags": ["web"], "available": True, "inputs": {}, "outputs": {}, "errors": []},
    ]

    with patch("agent.react_executor.OpenAI", return_value=client):
        with patch("agent.react_executor.check_cost_ceiling"):
            trace = react_execute("simple goal", tools, metadata, plan_hint=None, max_steps=10)

    assert trace.halted_for is None
    assert trace.final_answer == "No plan needed."


# ── 10. Plan_hint with bogus tools ────────────────────────────────────────


def test_plan_hint_with_bogus_tools():
    """Pass a plan whose tools don't exist; ReAct adapts."""
    plan = _make_plan([
        {"id": "t1", "goal": "do something", "tool": "nonexistent_tool", "inputs": {}},
    ])
    responses = [
        _mock_response(tool_calls=[{"name": "web_search", "args": {"query": "alternative"}}], finish_reason="tool_calls"),
        _mock_response(content="Adapted from bad plan.", finish_reason="stop"),
    ]
    client = _mock_client(responses)

    tools = {"web_search": lambda args: {"result": {"results": []}}}
    metadata = [
        {"name": "web_search", "description": "Search", "tags": ["web"], "available": True, "inputs": {}, "outputs": {}, "errors": []},
    ]

    with patch("agent.react_executor.OpenAI", return_value=client):
        with patch("agent.react_executor.check_cost_ceiling"):
            trace = react_execute("goal with bad plan", tools, metadata, plan_hint=plan, max_steps=10)

    assert trace.halted_for is None
    assert trace.final_answer == "Adapted from bad plan."


# ── 11. Observation truncation ────────────────────────────────────────────


def test_observation_truncation():
    """Tool returns 50 KB string; observation in messages is <=8KB; full output preserved in trace.steps."""
    big_output = "x" * 50_000
    responses = [
        _mock_response(tool_calls=[{"name": "crawl4ai", "args": {"url": "http://big.com"}}], finish_reason="tool_calls"),
        _mock_response(content="Done.", finish_reason="stop"),
    ]
    client = _mock_client(responses)

    tools = {"crawl4ai": lambda args: {"result": {"markdown": big_output, "url": "http://big.com"}}}
    metadata = [
        {"name": "crawl4ai", "description": "Crawl", "tags": ["web"], "available": True, "inputs": {}, "outputs": {}, "errors": []},
    ]

    with patch("agent.react_executor.OpenAI", return_value=client):
        with patch("agent.react_executor.check_cost_ceiling"):
            trace = react_execute("Crawl big page", tools, metadata, plan_hint=None, max_steps=10, max_observation_chars=8000)

    # Full output preserved in trace step observation
    step = trace.steps[0]
    assert step["observation"]["result"]["markdown"] == big_output
    # Preview is truncated
    assert len(step["observation_preview"]) <= 403  # 400 + "..."


# ── 12. Context compaction ────────────────────────────────────────────────


def test_context_compaction():
    """Drive enough steps that the soft cap triggers; verify oldest tool turns are dropped but system+user persist."""
    messages = [
        {"role": "system", "content": "You are an agent."},
        {"role": "user", "content": "Do the thing."},
    ]
    # Add many tool turns to exceed soft cap
    for i in range(20):
        messages.append({"role": "assistant", "content": f"step {i}", "tool_calls": []})
        messages.append({"role": "tool", "content": "x" * 2000, "tool_call_id": f"call_{i}"})

    compacted = _compact_if_oversize(messages, soft_cap_tokens=5000)

    # System and user preserved
    assert compacted[0]["role"] == "system"
    assert compacted[1]["role"] == "user"
    # Some middle messages were dropped
    assert len(compacted) < len(messages)
    assert len(compacted) > 2


# ── Helper tests ──────────────────────────────────────────────────────────


def test_hash_args_deterministic():
    assert _hash_args({"a": 1, "b": 2}) == _hash_args({"b": 2, "a": 1})
    assert _hash_args({"a": 1}) != _hash_args({"a": 2})


def test_serialize_observation_truncates():
    obs = {"result": {"data": "x" * 10_000}}
    serialized = _serialize_observation(obs, max_chars=500)
    assert "truncated" in serialized
    assert len(serialized) < 10_000  # definitely truncated


def test_preview_truncates():
    obs = {"result": {"data": "x" * 1000}}
    preview = _preview(obs, max_chars=100)
    assert len(preview) <= 103  # 100 + "..."


def test_estimate_tokens_basic():
    msg = {"role": "user", "content": "hello world"}
    tokens = _estimate_tokens(msg)
    assert 1 <= tokens <= 10


def test_format_user_message_includes_tools():
    metadata = [{"name": "web_search", "description": "Search", "tags": ["web"], "available": True}]
    msg = _format_user_message("find stuff", None, metadata)
    assert "find stuff" in msg
    assert "web_search" in msg


def test_plan_to_dict():
    plan = _make_plan([{"id": "t1", "goal": "do it", "tool": "web_search", "inputs": {}}])
    d = _plan_to_dict(plan)
    assert d["goal"] == "test goal"
    assert len(d["suggested_tasks"]) == 1
    assert d["suggested_tasks"][0]["tool"] == "web_search"


def test_no_tools_available_halts():
    """When tool_metadata is empty, react_execute returns NO_TOOLS_AVAILABLE."""
    trace = react_execute("goal", {}, [], plan_hint=None, max_steps=10)
    assert trace.halted_for == "NO_TOOLS_AVAILABLE"


def test_model_error_halts():
    """When the model call raises, trace halts with MODEL_ERROR."""
    client = Mock()
    client.chat.completions.create = Mock(side_effect=RuntimeError("API down"))

    tools = {"web_search": lambda args: {"result": {}}}
    metadata = [
        {"name": "web_search", "description": "Search", "tags": ["web"], "available": True, "inputs": {}, "outputs": {}, "errors": []},
    ]

    with patch("agent.react_executor.OpenAI", return_value=client):
        with patch("agent.react_executor.check_cost_ceiling"):
            trace = react_execute("goal", tools, metadata, plan_hint=None, max_steps=10)

    assert trace.halted_for == "MODEL_ERROR"
    assert trace.steps[0]["kind"] == "model_error"
