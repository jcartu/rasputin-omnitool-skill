"""Skipped placeholder tests for agent loop integration."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="PHASE-2 scaffold only; loop wiring lands in later phases")


def test_planner_executor_reviewer_loop_placeholder() -> None:
    pass


def test_observability_trace_loop_placeholder() -> None:
    pass
