"""Tests for the v0.4 plugin auto-discovery system."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.tool_registry import discover_tools, load_tools, load_tool_definitions, ToolDefinition


def test_all_existing_tools_discoverable():
    tools = discover_tools()
    expected = {"catalog", "docling", "crawl4ai", "sandbox", "browser",
                "deliverables", "tts", "stt", "image_gen", "video_gen",
                "music_gen", "memory"}
    assert set(tools.keys()) >= expected, f"missing: {expected - set(tools.keys())}"


def test_each_discovered_tool_has_callable_run():
    tools = discover_tools()
    for name, tool in tools.items():
        assert callable(tool.run), f"{name}.run not callable"
        assert isinstance(tool, ToolDefinition)


def test_discovered_tools_have_valid_manifests():
    tools = discover_tools()
    for name, tool in tools.items():
        if tool.invalid_reason:
            pytest.fail(f"{name} invalid: {tool.invalid_reason}")
        assert tool.schema["name"] == name
        assert tool.version
        assert tool.description


def test_load_tools_returns_callable_dict():
    """Backward compat: load_tools() returns dict[str, Callable]."""
    tools = load_tools()
    assert isinstance(tools, dict)
    assert len(tools) == 18
    for name, run in tools.items():
        assert callable(run)


def test_load_tool_definitions_returns_definitions():
    defs = load_tool_definitions()
    assert isinstance(defs, dict)
    for name, tool in defs.items():
        assert isinstance(tool, ToolDefinition)


def test_invalid_manifest_marked_invalid_not_crashed(tmp_path, monkeypatch):
    fake_tools = tmp_path / "tools"
    fake_tools.mkdir()
    bad = fake_tools / "broken_tool"
    bad.mkdir()
    (bad / "manifest.json").write_text("{not valid json")
    (bad / "index.py").write_text("def run(i): return {}")

    tools = discover_tools(tools_dir=fake_tools)
    assert "broken_tool" in tools
    assert not tools["broken_tool"].available
    assert "manifest invalid" in tools["broken_tool"].invalid_reason


def test_missing_index_py_marked_invalid(tmp_path):
    fake_tools = tmp_path / "tools"
    fake_tools.mkdir()
    bad = fake_tools / "no_index"
    bad.mkdir()
    (bad / "manifest.json").write_text(json.dumps({
        "name": "no_index", "version": "0.1.0",
        "description": "broken on purpose",
        "inputs": {}, "outputs": {}, "errors": ["X"]
    }))
    tools = discover_tools(tools_dir=fake_tools)
    assert not tools["no_index"].available
    assert "missing index.py" in tools["no_index"].invalid_reason


def test_name_mismatch_marked_invalid(tmp_path):
    fake_tools = tmp_path / "tools"
    fake_tools.mkdir()
    bad = fake_tools / "real_name"
    bad.mkdir()
    (bad / "manifest.json").write_text(json.dumps({
        "name": "wrong_name", "version": "0.1.0",
        "description": "name mismatch",
        "inputs": {}, "outputs": {}, "errors": ["X"]
    }))
    (bad / "index.py").write_text("def run(i): return {}")
    tools = discover_tools(tools_dir=fake_tools)
    assert not tools["real_name"].available
    assert "manifest name" in tools["real_name"].invalid_reason


def test_skill_manifest_in_sync():
    """The committed manifest.json must match what regenerate produces."""
    import subprocess
    result = subprocess.run(
        ["python", "scripts/regenerate-skill-manifest.py", "--check"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"manifest out of sync:\n{result.stdout}\n{result.stderr}"
