"""Tests for tool backend health probing."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, Mock


from agent.tool_registry import probe_backends, ToolDefinition


def _make_tool(name: str, schema: dict) -> ToolDefinition:
    return ToolDefinition(
        name=name, version="0.1.0", description="test",
        schema=schema, run=lambda i: {"result": {}},
        source_dir=Path("/tmp"),
    )


def test_tool_with_healthy_backend_stays_available():
    tool = _make_tool("test_tool", {
        "backends": [{"name": "service", "health_url": "http://localhost:9999/health", "required": True}]
    })
    with patch("httpx.get") as mock:
        mock.return_value = Mock(status_code=200)
        result = probe_backends({"test_tool": tool})
    assert result["test_tool"].available is True
    assert result["test_tool"].backend_statuses[0].available is True


def test_required_backend_down_marks_unavailable():
    tool = _make_tool("test_tool", {
        "backends": [{"name": "service", "health_url": "http://localhost:9999/health", "required": True}]
    })
    with patch("httpx.get") as mock:
        mock.side_effect = Exception("connection refused")
        result = probe_backends({"test_tool": tool})
    assert result["test_tool"].available is False
    assert result["test_tool"].backend_statuses[0].available is False
    assert "connection refused" in result["test_tool"].backend_statuses[0].message


def test_optional_backend_down_keeps_available():
    tool = _make_tool("test_tool", {
        "backends": [{"name": "fallback", "health_url": "http://localhost:9999/health", "required": False}]
    })
    with patch("httpx.get") as mock:
        mock.side_effect = Exception("nope")
        result = probe_backends({"test_tool": tool})
    assert result["test_tool"].available is True


def test_tool_with_no_backends_stays_available():
    tool = _make_tool("test_tool", {})
    result = probe_backends({"test_tool": tool})
    assert result["test_tool"].available is True
    assert result["test_tool"].backend_statuses == []


def test_multiple_backends_all_required():
    tool = _make_tool("test_tool", {
        "backends": [
            {"name": "a", "health_url": "http://localhost:9001/health", "required": True},
            {"name": "b", "health_url": "http://localhost:9002/health", "required": True},
        ]
    })
    with patch("httpx.get") as mock:
        responses = [Mock(status_code=200), Exception("down")]
        mock.side_effect = responses
        result = probe_backends({"test_tool": tool})
    assert result["test_tool"].available is False
