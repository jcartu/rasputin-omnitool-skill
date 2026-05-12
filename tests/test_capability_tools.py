"""Tests for the remaining PHASE-5 capability tools."""
from __future__ import annotations

from unittest.mock import patch, Mock


# ---- web_search ----

class TestWebSearch:
    def test_missing_query_returns_error(self):
        from tools.web_search.index import run
        result = run({})
        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"

    def test_searxng_unreachable_returns_error(self):
        from tools.web_search.index import run
        with patch("tools.web_search.index.httpx") as mock_httpx:
            mock_httpx.ConnectError = Exception
            mock_httpx.get.side_effect = Exception("connection refused")
            result = run({"query": "test"})
        assert "error" in result
        assert result["error"]["code"] == "SEARXNG_UNREACHABLE"

    def test_search_returns_results(self):
        from tools.web_search.index import run
        fake_resp = Mock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {
            "results": [
                {"title": "Result 1", "url": "http://example.com", "content": "Snippet 1"},
            ]
        }
        with patch("tools.web_search.index.httpx") as mock_httpx:
            mock_httpx.get.return_value = fake_resp
            result = run({"query": "test"})
        assert "result" in result
        assert len(result["result"]["results"]) == 1
        assert result["result"]["results"][0]["title"] == "Result 1"


# ---- slides ----

class TestSlides:
    def test_missing_markdown_returns_error(self):
        from tools.slides.index import run
        result = run({})
        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"

    def test_invalid_format_returns_error(self):
        from tools.slides.index import run
        result = run({"markdown": "# Hello", "format": "docx"})
        assert "error" in result
        assert result["error"]["code"] == "INVALID_FORMAT"

    def test_marp_not_installed_returns_error(self):
        from tools.slides.index import run
        with patch("tools.slides.index.subprocess") as mock_sub:
            mock_sub.run.side_effect = FileNotFoundError()
            result = run({"markdown": "# Hello"})
        assert "error" in result
        assert result["error"]["code"] == "MARP_NOT_INSTALLED"


# ---- mail ----

class TestMail:
    def test_invalid_operation_returns_error(self):
        from tools.mail.index import run
        result = run({"operation": "delete"})
        assert "error" in result
        assert result["error"]["code"] == "INVALID_OPERATION"

    def test_himalaya_not_installed_returns_error(self):
        from tools.mail.index import run
        with patch("tools.mail.index.subprocess") as mock_sub:
            mock_sub.run.side_effect = FileNotFoundError()
            result = run({"operation": "send", "to": "test@example.com"})
        assert "error" in result
        assert result["error"]["code"] == "HIMALAYA_NOT_INSTALLED"


# ---- coding_agent ----

class TestCodingAgent:
    def test_missing_task_returns_error(self):
        from tools.coding_agent.index import run
        result = run({})
        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"

    def test_aider_not_installed_returns_error(self):
        from tools.coding_agent.index import run
        with patch("tools.coding_agent.index.subprocess") as mock_sub:
            mock_sub.run.side_effect = FileNotFoundError()
            result = run({"task": "fix bug"})
        assert "error" in result
        assert result["error"]["code"] == "AIDER_NOT_INSTALLED"
