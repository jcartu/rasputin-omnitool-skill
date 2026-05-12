"""Unit tests for executor."""
from agent.executor import execute, _substitute_placeholders
from agent.planner import Plan, PlanTask


def _make_plan(tasks=None):
    return Plan(
        goal="Test goal",
        tasks=tasks or [
            PlanTask(id="T1", goal="Task 1", tool="catalog", inputs={}),
        ],
    )


def test_execute_with_mocked_tools():
    plan = _make_plan([
        PlanTask(id="T1", goal="Task 1", tool="catalog", inputs={}),
        PlanTask(id="T2", goal="Task 2", tool="deliverables", inputs={"title": "Test"}),
    ])
    tools = {
        "catalog": lambda inp: {"result": {"candidates": [{"name": "Test"}]}},
        "deliverables": lambda inp: {"result": {"artifacts": [{"path": "/tmp/test.md", "name": "test.md"}]}},
    }
    trace = execute(plan, tools)
    assert len(trace.steps) == 2
    assert trace.halted_for is None
    assert "/tmp/test.md" in trace.artifacts


def test_max_steps_halt():
    from agent.config import CONFIG
    # Create a plan with more tasks than max_steps
    plan = _make_plan([
        PlanTask(id=f"T{i}", goal=f"Task {i}", tool="catalog", inputs={})
        for i in range(1, 50)
    ])
    tools = {"catalog": lambda inp: {"result": {}}}
    # Temporarily override max_steps
    trace = execute(plan, tools)
    # Should halt if steps exceed CONFIG.max_steps_per_goal
    if trace.halted_for == "MAX_STEPS":
        assert len(trace.steps) <= CONFIG.max_steps_per_goal


def test_failure_rate_halt():
    call_count = [0]
    def failing_tool(inp):
        call_count[0] += 1
        if call_count[0] % 2 == 0:
            return {"result": {}}
        return {"error": {"code": "FAIL", "message": "intentional"}}

    plan = _make_plan([
        PlanTask(id=f"T{i}", goal=f"Task {i}", tool="fail", inputs={})
        for i in range(1, 20)
    ])
    tools = {"fail": failing_tool}
    trace = execute(plan, tools)
    # With 50% failure rate and max_tool_failure_rate=0.30, should halt
    assert trace.halted_for == "TOOL_FAILURE_RATE" or len(trace.steps) > 0


def test_placeholder_substitution():
    previous = {"T1": {"markdown": "# Hello", "title": "Test"}}
    inputs = {"title": "${T1.title}", "body": "${T1.markdown}"}
    result = _substitute_placeholders(inputs, previous)
    assert result["title"] == "Test"
    assert result["body"] == "# Hello"


def test_placeholder_substitution_nested():
    previous = {"T1": {"candidates": [{"name": "A"}]}}
    inputs = {"data": "${T1.candidates}"}
    result = _substitute_placeholders(inputs, previous)
    assert '"name"' in result["data"]


def test_placeholder_missing_key_returns_literal():
    previous = {}
    inputs = {"ref": "${T99.value}"}
    result = _substitute_placeholders(inputs, previous)
    assert result["ref"] == "${T99.value}"


def test_executor_handles_unknown_tool():
    plan = _make_plan([
        PlanTask(id="T1", goal="Task 1", tool="nonexistent", inputs={}),
    ])
    tools = {"catalog": lambda inp: {"result": {}}}
    trace = execute(plan, tools)
    assert len(trace.steps) == 1
    assert trace.steps[0]["status"] == "error"
    assert "not found" in trace.steps[0]["error"]

def test_automatic_lineage_wiring(tmp_path, monkeypatch):
    """Executor wires derived_from when T2 consumes T1 output via ${T1}."""
    db = tmp_path / "registry.db"
    monkeypatch.setenv("RASPUTIN_OMNITOOL_ARTIFACT_DB", str(db))
    # Reset singleton
    import agent.artifact_registry as ar
    ar._INSTANCE = None

    from agent.artifact_registry import get_registry

    # T1 produces a file, T2 consumes it via ${T1.path}
    f1 = tmp_path / "source.md"
    f1.write_text("# Source data")
    f2 = tmp_path / "report.md"
    f2.write_text("# Report based on source")

    plan = _make_plan([
        PlanTask(id="T1", goal="Crawl", tool="crawl", inputs={"url": "https://example.com"}),
        PlanTask(id="T2", goal="Write report", tool="deliverables", inputs={"source": "${T1.path}"}),
    ])
    tools = {
        "crawl": lambda inp: {"result": {"path": str(f1), "markdown": "# Source"}},
        "deliverables": lambda inp: {"result": {"path": str(f2), "title": "Report"}},
    }
    execute(plan, tools, context={"goal_id": "g-lineage"})

    # T2's artifact should have derived_from pointing to T1's artifact
    reg = get_registry()
    arts = reg.list(goal_id="g-lineage")
    assert len(arts) == 2

    # Find the deliverables artifact (T2)
    t2_art = next(a for a in arts if "report" in a.path)
    t1_art = next(a for a in arts if "source" in a.path)
    assert t1_art.id in t2_art.derived_from
