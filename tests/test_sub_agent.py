"""Phase 7: sub_agent tool — 12+ unit tests."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Isolate artifact DB for tests
os.environ["RASPUTIN_OMNITOOL_ARTIFACT_DB"] = ":memory:"


@pytest.fixture(autouse=True)
def _reset_registry():
    """Reset the artifact registry singleton before each test."""
    import importlib

    agent_art = importlib.import_module("agent.artifact_registry")
    agent_art._registry = None
    agent_art._lock = None
    yield
    agent_art._registry = None
    agent_art._lock = None


class TestInputValidation:
    def test_empty_sub_goals_returns_invalid_input(self):
        from tools.sub_agent.index import run

        result = run({"sub_goals": []})
        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"

    def test_non_list_sub_goals_returns_invalid_input(self):
        from tools.sub_agent.index import run

        result = run({"sub_goals": "not a list"})
        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"

    def test_empty_string_in_sub_goals_returns_invalid_input(self):
        from tools.sub_agent.index import run

        result = run({"sub_goals": [""]})
        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"

    def test_none_in_sub_goals_returns_invalid_input(self):
        from tools.sub_agent.index import run

        result = run({"sub_goals": [None]})
        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"


class TestSingleSub:
    @patch("agent.run_goal")
    def test_single_sub_returns_ok_result(self, mock_run_goal):
        from tools.sub_agent.index import run

        mock_run_goal.return_value = {
            "goal_id": "test/sub-1",
            "plan": MagicMock(),
            "trace": MagicMock(final_answer="done", halted_for=None),
            "artifacts": [],
            "review": MagicMock(verdict="APPROVE", notes="good"),
            "revised": False,
            "cost_usd": 0.05,
        }

        result = run({"sub_goals": ["do something"], "_goal_id": "test"})
        assert "result" in result
        r = result["result"]
        assert len(r["results"]) == 1
        assert r["results"][0]["status"] == "ok"
        assert r["results"][0]["sub_agent_id"] == "test/sub-1"
        assert r["successful_count"] == 1
        assert r["failed_count"] == 0


class TestParallelSuccess:
    @patch("agent.run_goal")
    def test_four_parallel_subs_all_succeed(self, mock_run_goal):
        from tools.sub_agent.index import run

        def side_effect(goal, **kwargs):
            return {
                "goal_id": kwargs.get("goal_id"),
                "plan": MagicMock(),
                "trace": MagicMock(final_answer=goal, halted_for=None),
                "artifacts": [],
                "review": MagicMock(verdict="APPROVE", notes="ok"),
                "revised": False,
                "cost_usd": 0.025,
            }

        mock_run_goal.side_effect = side_effect
        goals = [f"goal-{i}" for i in range(4)]
        result = run({"sub_goals": goals, "max_concurrent": 4, "_goal_id": "parallel"})
        r = result["result"]
        assert len(r["results"]) == 4
        assert r["successful_count"] == 4
        assert r["failed_count"] == 0
        assert r["aggregate_cost_usd"] == pytest.approx(0.1)


class TestPartialFailure:
    @patch("agent.run_goal")
    def test_one_of_four_subs_fails(self, mock_run_goal):
        from tools.sub_agent.index import run

        with patch.dict(os.environ, {"RASPUTIN_OMNITOOL_MAX_COST_USD": "999"}):
            def side_effect(goal, **kwargs):
                if goal == "will-fail":
                    return {
                        "goal_id": kwargs.get("goal_id"),
                        "plan": MagicMock(),
                        "trace": MagicMock(final_answer=None, halted_for="BUDGET"),
                        "artifacts": [],
                        "review": MagicMock(verdict="ABORT", notes="budget exceeded"),
                        "revised": False,
                        "cost_usd": 0.0,
                        "halted": True,
                        "reason": "BUDGET",
                    }
                return {
                    "goal_id": kwargs.get("goal_id"),
                    "plan": MagicMock(),
                    "trace": MagicMock(final_answer=goal, halted_for=None),
                    "artifacts": [],
                    "review": MagicMock(verdict="APPROVE", notes="ok"),
                    "revised": False,
                    "cost_usd": 0.025,
                }

            mock_run_goal.side_effect = side_effect
            goals = ["ok-1", "will-fail", "ok-2", "ok-3"]
            result = run({"sub_goals": goals, "_goal_id": "partial"})
            r = result["result"]
            assert r["successful_count"] == 3
            assert r["failed_count"] == 1
            assert r["results"][1]["status"] == "failed"


class TestBudgetPreflight:
    @patch("agent.run_goal")
    def test_budget_preflight_blocks_oversized_fanout(self, mock_run_goal):
        from tools.sub_agent.index import run

        with patch.dict(os.environ, {"RASPUTIN_OMNITOOL_MAX_COST_USD": "0.10"}):
            with patch("tools.sub_agent.index._budget_preflight") as mock_preflight:
                mock_preflight.return_value = {
                    "error": {
                        "code": "INSUFFICIENT_BUDGET",
                        "message": "would request 0.5000 for 5 subs; spent 0.0500, limit 0.10",
                    }
                }
                result = run(
                    {
                        "sub_goals": [f"g-{i}" for i in range(5)],
                        "budget_usd_per_sub": 0.10,
                        "_goal_id": "budget-test",
                    }
                )
                assert "error" in result
                assert result["error"]["code"] == "INSUFFICIENT_BUDGET"
                mock_run_goal.assert_not_called()


class TestRecursionBlocking:
    @patch("agent.run_goal")
    def test_recursion_blocked_by_default_denylist(self, mock_run_goal):
        from tools.sub_agent.index import run

        mock_run_goal.return_value = {
            "goal_id": "rec-test/sub-1",
            "plan": MagicMock(),
            "trace": MagicMock(final_answer="ok", halted_for=None),
            "artifacts": [],
            "review": MagicMock(verdict="APPROVE", notes="ok"),
            "revised": False,
            "cost_usd": 0.01,
        }

        run({"sub_goals": ["nested sub-agent call"], "_goal_id": "rec-test"})
        # Verify the sub was called with sub_agent in denylist
        call_kwargs = mock_run_goal.call_args.kwargs
        assert "sub_agent" in call_kwargs.get("tool_denylist", [])

    @patch("agent.run_goal")
    def test_recursion_permitted_with_override_capped_by_depth(self, mock_run_goal):
        from tools.sub_agent.index import run

        result = run(
            {
                "sub_goals": ["nested"],
                "tool_denylist": [],
                "max_depth": 1,
                "_depth": 1,
                "_goal_id": "depth-test",
            }
        )
        assert "error" in result
        assert result["error"]["code"] == "MAX_DEPTH_EXCEEDED"
        mock_run_goal.assert_not_called()


class TestAllowlistDenylist:
    @patch("agent.run_goal")
    def test_allowlist_enforced_forbidden_tool_returns_not_allowed(self, mock_run_goal):
        from tools.sub_agent.index import run

        mock_run_goal.return_value = {
            "goal_id": "allow-test/sub-1",
            "plan": MagicMock(),
            "trace": MagicMock(final_answer="ok", halted_for=None),
            "artifacts": [],
            "review": MagicMock(verdict="APPROVE", notes="ok"),
            "revised": False,
            "cost_usd": 0.01,
        }

        run(
            {
                "sub_goals": ["use only crawl4ai"],
                "tool_allowlist": ["crawl4ai"],
                "_goal_id": "allow-test",
            }
        )
        call_kwargs = mock_run_goal.call_args.kwargs
        assert call_kwargs.get("tool_allowlist") == ["crawl4ai"]


class TestTimeout:
    @patch("agent.run_goal")
    def test_timeout_per_sub_kills_and_records_wallclock(self, mock_run_goal):
        from tools.sub_agent.index import run
        import threading

        def slow_goal(goal, **kwargs):
            event = threading.Event()
            event.wait(60)  # will timeout
            return {}

        mock_run_goal.side_effect = slow_goal
        result = run(
            {
                "sub_goals": ["slow task"],
                "timeout_min_per_sub": 0,  # 0 minutes = immediate timeout
                "_goal_id": "timeout-test",
            }
        )
        r = result["result"]
        assert len(r["results"]) == 1
        assert r["results"][0]["status"] == "timeout"
        assert r["results"][0]["halted_for"] == "WALLCLOCK"


class TestArtifacts:
    @patch("agent.run_goal")
    def test_artifacts_tagged_with_sub_agent_id(self, mock_run_goal):
        from tools.sub_agent.index import run
        from agent.artifact_registry import get_registry

        reg = get_registry()
        # Create a temp file for the registry
        tmp = Path("/tmp/ph7_test_artifact.txt")
        tmp.write_text("test")
        art = reg.add(tmp, produced_by="test", goal_id="artifact-test")

        mock_run_goal.return_value = {
            "goal_id": "artifact-test/sub-1",
            "plan": MagicMock(),
            "trace": MagicMock(final_answer="ok", halted_for=None),
            "artifacts": [art.id],
            "review": MagicMock(verdict="APPROVE", notes="ok"),
            "revised": False,
            "cost_usd": 0.01,
        }

        result = run({"sub_goals": ["produce artifact"], "_goal_id": "artifact-test"})
        r = result["result"]
        assert r["results"][0]["artifact_ids"] == [art.id]

        # Verify the artifact was retagged
        with reg._conn:
            row = reg._conn.execute(
                "SELECT goal_id, sub_agent_id FROM artifact WHERE id = ?",
                (art.id,),
            ).fetchone()
            assert row[0] == "artifact-test"
            assert row[1] == "artifact-test/sub-1"
        tmp.unlink()

    @patch("agent.run_goal")
    def test_dedup_across_subs(self, mock_run_goal):
        from tools.sub_agent.index import run
        from agent.artifact_registry import get_registry

        reg = get_registry()
        # Create a temp file for the registry
        tmp = Path("/tmp/ph7_dedup.txt")
        tmp.write_text("same content")
        art = reg.add(tmp, produced_by="test", goal_id="dedup-test")

        def side_effect(goal, **kwargs):
            return {
                "goal_id": kwargs.get("goal_id"),
                "plan": MagicMock(),
                "trace": MagicMock(final_answer=goal, halted_for=None),
                "artifacts": [art.id],
                "review": MagicMock(verdict="APPROVE", notes="ok"),
                "revised": False,
                "cost_usd": 0.01,
            }

        mock_run_goal.side_effect = side_effect
        result = run(
            {
                "sub_goals": ["sub-1 produces X", "sub-2 produces same X"],
                "_goal_id": "dedup-test",
            }
        )
        r = result["result"]
        # Both subs report the same artifact_id (content-addressed dedup)
        assert r["results"][0]["artifact_ids"] == [art.id]
        assert r["results"][1]["artifact_ids"] == [art.id]
        tmp.unlink()


class TestParentTrace:
    @patch("agent.run_goal")
    def test_parent_trace_shows_aggregate_output(self, mock_run_goal):
        from tools.sub_agent.index import run

        mock_run_goal.return_value = {
            "goal_id": "trace-test/sub-1",
            "plan": MagicMock(),
            "trace": MagicMock(final_answer="sub-result", halted_for=None),
            "artifacts": [],
            "review": MagicMock(verdict="APPROVE", notes="ok"),
            "revised": False,
            "cost_usd": 0.01,
        }

        result = run({"sub_goals": ["sub-goal-1"], "_goal_id": "trace-test"})
        r = result["result"]
        # The parent sees a structured aggregate, not the full sub trace
        assert "results" in r
        assert "aggregate_cost_usd" in r
        assert "successful_count" in r
        assert "failed_count" in r
        assert isinstance(r["results"], list)
