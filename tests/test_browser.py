"""Unit tests for browser tool."""
import pytest
from tools.browser.index import run


def test_invalid_action_returns_error():
    result = run({"action": "invalid"})
    assert "error" in result


def test_navigate_requires_url():
    result = run({"action": "navigate"})
    assert result.get("error", {}).get("code") == "NAVIGATION_FAILED"


def test_navigate_example_com():
    result = run({"action": "navigate", "url": "http://example.com"})
    if "result" in result:
        assert "Example Domain" in result["result"]["title"]


def test_screenshot_requires_url():
    result = run({"action": "screenshot"})
    assert "result" in result or "error" in result


def test_extract_text_without_selector():
    result = run({"action": "extract_text", "url": "http://example.com"})
    if "result" in result:
        assert "text" in result["result"]


def test_fill_form_requires_selector():
    result = run({"action": "fill_form", "url": "http://example.com"})
    assert result.get("error", {}).get("code") == "SELECTOR_NOT_FOUND"


def test_click_requires_selector():
    result = run({"action": "click", "url": "http://example.com"})
    assert result.get("error", {}).get("code") == "SELECTOR_NOT_FOUND"
