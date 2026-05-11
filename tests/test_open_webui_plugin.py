"""Smoke test: the Open WebUI plugin module is importable and the Tools class is well-formed."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

PLUGIN_PATH = Path(__file__).parent.parent / "surfaces/open-webui/rasputin_function.py"


def _load_plugin():
    spec = importlib.util.spec_from_file_location("rasputin_function", PLUGIN_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_plugin_imports():
    mod = _load_plugin()
    assert hasattr(mod, "Tools")


def test_plugin_has_run_goal_method():
    mod = _load_plugin()
    tools = mod.Tools()
    assert hasattr(tools, "run_goal")
    assert callable(tools.run_goal)


def test_plugin_valves_have_max_cost_usd():
    mod = _load_plugin()
    tools = mod.Tools()
    assert tools.valves.max_cost_usd > 0


def test_format_response_handles_halted():
    mod = _load_plugin()
    tools = mod.Tools()
    out = tools._format_response({
        "halted": True,
        "reason": "cost_ceiling_exceeded",
        "details": {"spent": 0.5, "limit": 0.10},
    })
    assert "halted" in out.lower()
    assert "cost_ceiling_exceeded" in out


def test_format_response_handles_approved():
    mod = _load_plugin()
    tools = mod.Tools()

    class FakeReview:
        verdict = "APPROVE"
        notes = "Found 3 tools."

    out = tools._format_response({
        "review": FakeReview(),
        "results": [
            {"result": {"artifact_path": "/tmp/report.md"}}
        ],
    })
    assert "APPROVE" in out
    assert "report.md" in out
