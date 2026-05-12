"""E2E tests for the ReAct executor — requires API key."""
from __future__ import annotations

import os
import time

import pytest

from agent.planner import Plan, PlanTask
from agent.react_executor import react_execute
from agent.tool_registry import load_tool_metadata


@pytest.mark.skipif(
    not os.environ.get("OPENCODE_ZEN_API_KEY"),
    reason="Requires OPENCODE_ZEN_API_KEY for real executor calls",
)
@pytest.mark.real_executor
def test_react_canary_crawl_example():
    """ReAct executor canary: crawl example.com and produce a summary."""
    goal = "Crawl example.com and produce a 1-paragraph markdown summary saved to outputs/."
    tools = {
        "crawl4ai": lambda args: {
            "result": {"markdown": "Example Domain\n\nThis domain is for use in documentation.", "url": "http://example.com"}
        },
        "deliverables": lambda args: {
            "result": {"path": "outputs/summary.md", "artifacts": [{"path": "outputs/summary.md"}]}
        },
    }
    metadata = load_tool_metadata(include_unavailable=True)
    # Filter to only the tools we have
    metadata = [m for m in metadata if m["name"] in tools]

    start = time.time()
    trace = react_execute(
        goal,
        tools,
        metadata,
        plan_hint=None,
        max_steps=10,
        budget_usd=0.50,
        max_wallclock_min=5,
    )
    elapsed = time.time() - start

    assert trace.halted_for is None, f"Trace halted: {trace.halted_for}"
    assert trace.final_answer is not None
    assert len(trace.steps) >= 1
    assert elapsed < 90, f"Took {elapsed:.1f}s, expected <90s"


@pytest.mark.skipif(
    not os.environ.get("OPENCODE_ZEN_API_KEY"),
    reason="Requires OPENCODE_ZEN_API_KEY for real executor calls",
)
@pytest.mark.real_executor
def test_react_adapts_to_bogus_plan():
    """ReAct executor adapts when planner hint contains bogus tools."""
    plan = Plan(
        goal="Search and summarize",
        tasks=[
            PlanTask(id="t1", goal="Use tts to speak", tool="tts", inputs={"text": "hello"}),
            PlanTask(id="t2", goal="Use video_gen", tool="video_gen", inputs={}),
        ],
        success_criteria=["done"],
    )
    tools = {
        "web_search": lambda args: {
            "result": {"results": [{"title": "Result", "url": "http://example.com"}]}
        },
    }
    metadata = [{"name": "web_search", "description": "Search", "tags": ["web"], "available": True, "inputs": {}, "outputs": {}, "errors": []}]

    trace = react_execute(
        "Search for something",
        tools,
        metadata,
        plan_hint=plan,
        max_steps=5,
        budget_usd=0.50,
    )

    # Should not halt on bogus plan — ReAct ignores plan_hint and uses available tools
    assert trace.halted_for in (None, "MAX_STEPS")
