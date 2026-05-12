"""Unit tests for browser tool."""
from unittest.mock import patch, MagicMock

from tools.browser.index import run


def test_invalid_action_returns_error():
    result = run({"action": "invalid", "session_id": None})
    assert result.get("error", {}).get("code") == "INVALID_OPERATION"


def test_navigate_requires_url():
    result = run({"action": "navigate", "session_id": None})
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

    result = run({"action": "navigate", "url": "http://example.com", "session_id": None})
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

    result = run({"action": "screenshot", "url": "http://example.com", "session_id": None})
    assert "result" in result
    assert "path" in result["result"]
    assert result["result"]["path"].endswith(".png")


@patch("playwright.sync_api.sync_playwright")
def test_fill_form_requires_selector(mock_sync_playwright):
    mock_pw = MagicMock()
    mock_context = MagicMock()
    mock_context.__enter__.return_value = mock_pw
    mock_context.__exit__.return_value = None
    mock_sync_playwright.return_value = mock_context
    result = run({"action": "fill_form", "url": "http://example.com", "session_id": None})
    assert result.get("error", {}).get("code") == "SELECTOR_NOT_FOUND"


@patch("playwright.sync_api.sync_playwright")
def test_click_requires_selector(mock_sync_playwright):
    mock_pw = MagicMock()
    mock_context = MagicMock()
    mock_context.__enter__.return_value = mock_pw
    mock_context.__exit__.return_value = None
    mock_sync_playwright.return_value = mock_context
    result = run({"action": "click", "url": "http://example.com", "session_id": None})
    assert result.get("error", {}).get("code") == "SELECTOR_NOT_FOUND"


@patch("playwright.sync_api.sync_playwright")
def test_evaluate_returns_result(mock_sync_playwright):
    mock_page = MagicMock()
    mock_page.url = "http://example.com"
    mock_page.goto.return_value = None
    mock_page.evaluate.return_value = 42

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

    result = run({
        "action": "evaluate",
        "expression": "2+2",
        "url": "http://example.com",
        "session_id": None,
    })
    assert "result" in result
    assert result["result"]["result"] == 42


@patch("playwright.sync_api.sync_playwright")
def test_wait_for_selector_returns_found(mock_sync_playwright):
    mock_page = MagicMock()
    mock_page.url = "http://example.com"
    mock_page.goto.return_value = None
    mock_page.wait_for_selector.return_value = True

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

    result = run({
        "action": "wait_for_selector",
        "selector": "#delayed-div",
        "url": "http://example.com",
        "session_id": None,
    })
    assert "result" in result
    assert result["result"]["found"] is True
