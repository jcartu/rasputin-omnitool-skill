"""Tests for Phase 8 event streaming."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from agent.event_stream import EventBus, StreamEvent, get_event_bus, redact_secrets
from agent.executor import ExecutionTrace
from agent.planner import Plan
from agent.react_executor import react_execute
from agent.reviewer import Review


def _event(type_: str = "test.event", goal_id: str = "g1", data: dict | None = None) -> StreamEvent:
    return StreamEvent(type_, datetime.now(timezone.utc), goal_id, None, data or {})


def _mock_response(
    content: str | None = None,
    tool_calls: list[dict] | None = None,
    finish_reason: str = "stop",
):
    msg = SimpleNamespace(content=content, tool_calls=[])
    if tool_calls:
        msg.tool_calls = [
            SimpleNamespace(
                id=f"call_{i}",
                function=SimpleNamespace(name=tc["name"], arguments=json.dumps(tc["args"])),
            )
            for i, tc in enumerate(tool_calls)
        ]
    return SimpleNamespace(
        choices=[SimpleNamespace(message=msg, finish_reason=finish_reason)],
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=50),
    )


def _metadata(name: str = "web_search") -> list[dict]:
    return [
        {
            "name": name,
            "description": "Test tool",
            "tags": [],
            "available": True,
            "inputs": {},
            "outputs": {},
            "errors": [],
        }
    ]


def test_stream_event_dataclass_shape():
    event = _event("goal.started", "goal-1", {"goal_text": "do it"})

    assert event.type == "goal.started"
    assert isinstance(event.timestamp, datetime)
    assert event.goal_id == "goal-1"
    assert event.sub_agent_id is None
    assert event.data == {"goal_text": "do it"}


def test_subscribe_sync_callback_fires_for_each_event_in_order():
    bus = EventBus()
    seen: list[str] = []

    bus.subscribe_sync(lambda event: seen.append(event.type))
    bus.emit(_event("first"))
    bus.emit(_event("second"))
    bus.emit(_event("third"))

    assert seen == ["first", "second", "third"]


def test_multiple_subscribers_all_receive_each_event():
    bus = EventBus()
    one: list[str] = []
    two: list[str] = []

    bus.subscribe_sync(lambda event: one.append(event.type))
    bus.subscribe_sync(lambda event: two.append(event.type))
    bus.emit(_event("goal.started"))
    bus.emit(_event("goal.completed"))

    assert one == ["goal.started", "goal.completed"]
    assert two == ["goal.started", "goal.completed"]


def test_unsubscribe_removes_subscriber_cleanly():
    bus = EventBus()
    seen: list[str] = []

    sub_id = bus.subscribe_sync(lambda event: seen.append(event.type))
    bus.emit(_event("before"))
    bus.unsubscribe(sub_id)
    bus.emit(_event("after"))

    assert seen == ["before"]


def test_subscriber_exception_does_not_block_other_subscribers():
    bus = EventBus()
    seen: list[str] = []

    def broken(_: StreamEvent) -> None:
        raise RuntimeError("boom")

    bus.subscribe_sync(broken)
    bus.subscribe_sync(lambda event: seen.append(event.type))
    bus.emit(_event("still-delivered"))

    assert seen == ["still-delivered"]


def test_redaction_replaces_secret_keys_recursively():
    redacted = redact_secrets(
        {
            "password": "pw",
            "api_key": "key",
            "Token": "tok",
            "nested": {"client-secret": "secret", "auth_header": "auth"},
            "items": [{"refresh_token": "refresh"}],
            "safe": "value",
        }
    )

    assert redacted["password"] == "***"
    assert redacted["api_key"] == "***"
    assert redacted["Token"] == "***"
    assert redacted["nested"] == {"client-secret": "***", "auth_header": "***"}
    assert redacted["items"] == [{"refresh_token": "***"}]
    assert redacted["safe"] == "value"


def test_emit_redacts_without_mutating_original_event_data():
    bus = EventBus()
    seen: list[StreamEvent] = []
    payload = {"inputs": {"api_key": "real", "query": "hello"}}

    bus.subscribe_sync(seen.append)
    bus.emit(_event("executor.tool_call_started", data=payload))

    assert seen[0].data["inputs"]["api_key"] == "***"
    assert payload["inputs"]["api_key"] == "real"


def test_get_event_bus_returns_singleton():
    assert get_event_bus() is get_event_bus()


def test_react_executor_emits_real_step_and_tool_events_in_order():
    events: list[StreamEvent] = []
    sub_id = get_event_bus().subscribe_sync(events.append)
    client = Mock()
    client.chat.completions.create = Mock(
        side_effect=[
            _mock_response(tool_calls=[{"name": "web_search", "args": {"query": "hello"}}], finish_reason="tool_calls"),
            _mock_response(content="Done", finish_reason="stop"),
        ]
    )

    try:
        with patch("agent.react_executor.OpenAI", return_value=client):
            with patch("agent.react_executor.check_cost_ceiling"):
                trace = react_execute(
                    "Search",
                    {"web_search": lambda args: {"result": {"hits": [args["query"]]}}},
                    _metadata("web_search"),
                    goal_id="g-react-order",
                    max_steps=5,
                )
    finally:
        get_event_bus().unsubscribe(sub_id)

    assert trace.final_answer == "Done"
    assert [event.type for event in events] == [
        "executor.step_started",
        "executor.tool_call_started",
        "executor.tool_call_completed",
        "executor.step_started",
    ]
    assert [event.goal_id for event in events] == ["g-react-order"] * 4


def test_react_executor_redacts_tool_inputs_but_tool_receives_real_value():
    events: list[StreamEvent] = []
    received_args: list[dict] = []
    sub_id = get_event_bus().subscribe_sync(events.append)
    client = Mock()
    client.chat.completions.create = Mock(
        side_effect=[
            _mock_response(
                tool_calls=[{"name": "secret_tool", "args": {"api_key": "real-key", "query": "hello"}}],
                finish_reason="tool_calls",
            ),
            _mock_response(content="Done", finish_reason="stop"),
        ]
    )

    def secret_tool(args: dict) -> dict:
        received_args.append(dict(args))
        return {"result": {"ok": True}}

    try:
        with patch("agent.react_executor.OpenAI", return_value=client):
            with patch("agent.react_executor.check_cost_ceiling"):
                react_execute("Use secret", {"secret_tool": secret_tool}, _metadata("secret_tool"), goal_id="g-secret")
    finally:
        get_event_bus().unsubscribe(sub_id)

    started = next(event for event in events if event.type == "executor.tool_call_started")
    assert started.data["inputs"] == {"api_key": "***", "query": "hello"}
    assert received_args == [{"api_key": "real-key", "query": "hello"}]


def test_react_executor_tool_completed_reports_error_status_for_unknown_tool():
    events: list[StreamEvent] = []
    sub_id = get_event_bus().subscribe_sync(events.append)
    client = Mock()
    client.chat.completions.create = Mock(
        side_effect=[
            _mock_response(tool_calls=[{"name": "missing", "args": {}}], finish_reason="tool_calls"),
            _mock_response(content="Recovered", finish_reason="stop"),
        ]
    )

    try:
        with patch("agent.react_executor.OpenAI", return_value=client):
            with patch("agent.react_executor.check_cost_ceiling"):
                react_execute("Use missing", {}, _metadata("missing"), goal_id="g-missing")
    finally:
        get_event_bus().unsubscribe(sub_id)

    completed = next(event for event in events if event.type == "executor.tool_call_completed")
    assert completed.data["tool_name"] == "missing"
    assert completed.data["status"] == "error"
    assert "UNKNOWN_TOOL" in completed.data["output_preview"]


def test_react_executor_no_tools_emits_goal_halted():
    events: list[StreamEvent] = []
    sub_id = get_event_bus().subscribe_sync(events.append)

    try:
        trace = react_execute("No tools", {}, [], goal_id="g-no-tools")
    finally:
        get_event_bus().unsubscribe(sub_id)

    assert trace.halted_for == "NO_TOOLS_AVAILABLE"
    assert events[-1].type == "goal.halted"
    assert events[-1].data["reason"] == "NO_TOOLS_AVAILABLE"


def test_run_goal_on_event_emits_started_completed_and_unsubscribes(monkeypatch):
    import agent

    events: list[StreamEvent] = []
    plan_obj = Plan(goal="Do it", tasks=[])
    trace = ExecutionTrace(plan=plan_obj, final_answer="done")

    monkeypatch.setattr(agent, "load_tool_metadata", lambda: [])
    monkeypatch.setattr(agent, "plan", lambda goal, tools_meta: plan_obj)
    monkeypatch.setattr(agent, "load_tools", lambda allowlist=None, denylist=None: {})
    monkeypatch.setattr(agent, "execute", lambda *args, **kwargs: trace)
    monkeypatch.setattr(agent, "review", lambda trace_arg, artifacts: Review("APPROVE", "ok", []))

    result = agent.run_goal("Do it", goal_id="g-run", on_event=events.append)
    get_event_bus().emit_typed("after.run", "g-run")

    assert result["goal_id"] == "g-run"
    assert [event.type for event in events] == ["goal.started", "goal.completed"]
    assert events[-1].data["verdict"] == "APPROVE"


def test_run_goal_halted_trace_emits_goal_halted_last(monkeypatch):
    import agent

    events: list[StreamEvent] = []
    plan_obj = Plan(goal="Do it", tasks=[])
    trace = ExecutionTrace(plan=plan_obj, halted_for="MAX_STEPS")

    monkeypatch.setattr(agent, "load_tool_metadata", lambda: [])
    monkeypatch.setattr(agent, "plan", lambda goal, tools_meta: plan_obj)
    monkeypatch.setattr(agent, "load_tools", lambda allowlist=None, denylist=None: {})
    monkeypatch.setattr(agent, "execute", lambda *args, **kwargs: trace)
    monkeypatch.setattr(agent, "review", lambda trace_arg, artifacts: Review("ABORT", "halted", []))

    result = agent.run_goal("Do it", goal_id="g-halt", on_event=events.append)

    assert result["trace"].halted_for == "MAX_STEPS"
    assert [event.type for event in events] == ["goal.started", "goal.halted"]
    assert events[-1].data["reason"] == "MAX_STEPS"
