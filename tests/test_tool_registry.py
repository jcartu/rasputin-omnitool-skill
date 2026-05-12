"""Tests for the v0.4 plugin auto-discovery system."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.tool_registry import (
    BackendStatus,
    ToolDefinition,
    discover_tools,
    invalidate_metadata_cache,
    load_tool_definitions,
    load_tool_metadata,
    load_tools,
)


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
        assert tool.schema["tags"]


def test_load_tools_returns_callable_dict():
    """Backward compat: load_tools() returns dict[str, Callable]."""
    tools = load_tools()
    assert isinstance(tools, dict)
    assert len(tools) == 17
    for name, run in tools.items():
        assert callable(run)


def test_load_tool_definitions_returns_definitions():
    defs = load_tool_definitions()
    assert isinstance(defs, dict)
    for name, tool in defs.items():
        assert isinstance(tool, ToolDefinition)


def test_load_tool_metadata_returns_non_empty_when_tools_exist():
    invalidate_metadata_cache()
    metadata = load_tool_metadata()
    assert metadata
    names = {entry["name"] for entry in metadata}
    assert {"catalog", "crawl4ai", "deliverables"} <= names
    for entry in metadata:
        assert entry["version"]
        assert entry["description"]
        assert entry["tags"]
        assert entry["available"] is True


def test_load_tool_metadata_ttl_cache_reuses_then_reprobes(monkeypatch):
    invalidate_metadata_cache()
    calls = {"count": 0}
    now = {"value": 100.0}

    def fake_discover_tools():
        calls["count"] += 1
        version = f"0.0.{calls['count']}"
        return {
            "fake": ToolDefinition(
                name="fake",
                version=version,
                description="fake tool",
                schema={
                    "name": "fake",
                    "version": version,
                    "description": "fake tool",
                    "inputs": {},
                    "outputs": {},
                    "errors": [],
                    "tags": ["test"],
                },
                run=lambda _inputs: {},
                source_dir=Path("fake"),
                available=True,
                backend_statuses=[BackendStatus(name="fake_backend", available=True, message="")],
            )
        }

    monkeypatch.setattr("agent.tool_registry.discover_tools", fake_discover_tools)
    monkeypatch.setattr("agent.tool_registry.probe_backends", lambda tools: tools)
    monkeypatch.setattr("agent.tool_registry.time.monotonic", lambda: now["value"])

    first = load_tool_metadata()
    second = load_tool_metadata()
    assert first is second
    assert calls["count"] == 1

    now["value"] += 31.0
    third = load_tool_metadata()
    assert third is not first
    assert calls["count"] == 2
    assert third[0]["version"] == "0.0.2"


def test_load_tool_metadata_include_unavailable_returns_broken_tools(monkeypatch):
    invalidate_metadata_cache()
    good = ToolDefinition(
        name="good",
        version="0.1.0",
        description="good tool",
        schema={
            "name": "good",
            "version": "0.1.0",
            "description": "good tool",
            "inputs": {},
            "outputs": {},
            "errors": [],
            "tags": ["ok"],
        },
        run=lambda _inputs: {},
        source_dir=Path("good"),
        available=True,
    )
    broken = ToolDefinition(
        name="broken",
        version="0.1.0",
        description="broken tool",
        schema={
            "name": "broken",
            "version": "0.1.0",
            "description": "broken tool",
            "inputs": {},
            "outputs": {},
            "errors": ["BROKEN"],
            "tags": ["broken"],
        },
        run=lambda _inputs: {},
        source_dir=Path("broken"),
        available=False,
        invalid_reason="broken on purpose",
    )
    monkeypatch.setattr("agent.tool_registry.discover_tools", lambda: {"good": good, "broken": broken})
    monkeypatch.setattr("agent.tool_registry.probe_backends", lambda tools: tools)

    available_only = load_tool_metadata()
    all_metadata = load_tool_metadata(include_unavailable=True)

    assert {entry["name"] for entry in available_only} == {"good"}
    assert {entry["name"] for entry in all_metadata} == {"broken", "good"}
    assert any(entry["available"] is False for entry in all_metadata)


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
        "inputs": {}, "outputs": {}, "errors": ["X"], "tags": ["test"]
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
        "inputs": {}, "outputs": {}, "errors": ["X"], "tags": ["test"]
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
