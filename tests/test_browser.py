"""Unit tests for browser tool."""
import pytest
from unittest.mock import patch, MagicMock
from tools.browser.index import run


def test_invalid_action_returns_error():
    result = run({"action": "invalid"})
    assert result.get("error", {}).get("code") == "INVALID_OPERATION"


def test_navigate_requires_url():
    result = run({"action": "navigate"})
    assert result.get("error", {}).get("code") == "NAVIGATION_FAILED"


@patch("playwright.sync_api.sync_playwright")
def test_navigate_example_com(mock_sync_playwright):
    mock_page = MagicMock()
    mock_page.url = "http://example.com"
    mock_page.title.return_value = "Example Domain"
    mock_response = MagicMock()
    mock_response.status = 200
    mock_page.goto.return_value = mock_response

    mock_browser = MagicMock()
    mock_browser.new_page.return_value = mock_page

    mock_chromium = MagicMock()
    mock_chromium.launch.return_value = mock_browser

    mock_pw = MagicMock()
    mock_pw.chromium = mock_chromium

    mock_context = MagicMock()
    mock_context.__enter__.return_value = mock_pw
    mock_context.__exit__.return_value = None
    mock_sync_playwright.return_value = mock_context

    result = run({"action": "navigate", "url": "http://example.com"})
    assert "result" in result
    assert result["result"]["title"] == "Example Domain"
    assert result["result"]["status"] == 200


@patch("playwright.sync_api.sync_playwright")
def test_screenshot_returns_path(mock_sync_playwright):
    mock_page = MagicMock()
    mock_page.url = "http://example.com"
    mock_page.goto.return_value = None

    mock_browser = MagicMock()
    mock_browser.new_page.return_value = mock_page

    mock_chromium = MagicMock()
    mock_chromium.launch.return_value = mock_browser

    mock_pw = MagicMock()
    mock_pw.chromium = mock_chromium

    mock_context = MagicMock()
    mock_context.__enter__.return_value = mock_pw
    mock_context.__exit__.return_value = None
    mock_sync_playwright.return_value = mock_context

    result = run({"action": "screenshot", "url": "http://example.com"})
    assert "result" in result
    assert "path" in result["result"]
    assert result["result"]["path"].endswith(".png")


def test_fill_form_requires_selector():
    result = run({"action": "fill_form", "url": "http://example.com"})
    assert result.get("error", {}).get("code") == "SELECTOR_NOT_FOUND"


def test_click_requires_selector():
    result = run({"action": "click", "url": "http://example.com"})
    assert result.get("error", {}).get("code") == "SELECTOR_NOT_FOUND"
