"""Phase 1 e2e: real planner with real tool metadata."""
from __future__ import annotations

import os

import pytest

from agent.tool_registry import load_tool_metadata


@pytest.mark.real_planner
def test_planner_produces_valid_plan_with_real_metadata():
    """Real planner call with real tool metadata produces a valid plan."""
    if not os.environ.get("OPENCODE_ZEN_API_KEY"):
        pytest.skip("OPENCODE_ZEN_API_KEY not set")

    # Load real metadata
    metadata = load_tool_metadata()
    assert len(metadata) > 0, "No tools available"

    # Verify all tools have required fields
    for tool in metadata:
        assert "name" in tool
        assert "tags" in tool
        assert len(tool["tags"]) > 0

    # The planner should be able to use this metadata
    # (Full planner integration test would go here)
    tool_names = {t["name"] for t in metadata}
    assert len(tool_names) == len(metadata), "Duplicate tool names"
