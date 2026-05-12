"""tools/browser/index.py — Operate a browser via Playwright with persistent sessions.

Inputs: action, url, selector, value, session_id, goal_id, headless, ...
Outputs: result (with session_id)
Errors: NAVIGATION_FAILED, SELECTOR_NOT_FOUND, TIMEOUT, SESSION_NOT_FOUND, SESSION_DEAD
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.browser_session import BrowserSession, get_browser_session_manager
from agent.config import CONFIG
from agent.artifact_registry import RegistryError, get_registry


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    action = inputs.get("action", "")
    valid_actions = (
        "navigate",
        "screenshot",
        "extract_text",
        "fill_form",
        "click",
        "wait_for_selector",
        "evaluate",
    )
    if action not in valid_actions:
        return {"error": {"code": "INVALID_OPERATION", "message": f"Unknown action: {action}"}}

    headless = inputs.get("headless", True)

    session: BrowserSession | None = None

    session: BrowserSession | None = None
    try:
        session = _resolve_session(inputs)
        if session is None:
            return _run_ephemeral(action, inputs, headless)

        mgr = get_browser_session_manager()
        result, storage_state = mgr.run_action(session, lambda page: _dispatch(action, page, inputs))
        mgr.save_storage_state(session.session_id, storage_state)
        return _with_session_id({"result": result}, session)

    except Exception as e:
        return _classify_error(e, action)


def _resolve_session(inputs: dict[str, Any]) -> BrowserSession | None:
    if "session_id" in inputs and inputs["session_id"] is None:
        return None

    manager = get_browser_session_manager()
    session_id = inputs.get("session_id")
    if session_id:
        return manager.attach(str(session_id))
    return manager.create(goal_id=inputs.get("goal_id"))


def _with_session_id(result: dict[str, Any], session: BrowserSession | None) -> dict[str, Any]:
    if session and "result" in result:
        result["result"]["session_id"] = session.session_id
    return result


def _dispatch(action: str, page: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    if action == "navigate":
        return _action_navigate(page, inputs)
    elif action == "screenshot":
        return _action_screenshot(page, inputs)
    elif action == "extract_text":
        return _action_extract_text(page, inputs)
    elif action == "fill_form":
        return _action_fill_form(page, inputs)
    elif action == "click":
        return _action_click(page, inputs)
    elif action == "wait_for_selector":
        return _action_wait_for_selector(page, inputs)
    elif action == "evaluate":
        return _action_evaluate(page, inputs)
    return {"error": {"code": "INVALID_OPERATION", "message": f"Unknown action: {action}"}}


def _action_navigate(page: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    url = inputs.get("url", "")
    if not url:
        raise ValueError("URL required")
    response = page.goto(url, timeout=30000)
    return {
        "final_url": page.url,
        "title": page.title(),
        "status": response.status if response else None,
    }


def _action_screenshot(page: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    url = inputs.get("url", "about:blank")
    page.goto(url, timeout=30000)
    screenshots_dir = Path(inputs.get("_screenshots_dir", CONFIG.outputs_dir))
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    from uuid import uuid4
    path = screenshots_dir / f"screenshot_{uuid4().hex}.png"
    page.screenshot(path=str(path))
    result = {"path": str(path), "title": page.title()}
    return _with_artifact(result, path, inputs.get("goal_id") or inputs.get("_goal_id"))


def _action_extract_text(page: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    url = inputs.get("url", "about:blank")
    selector = inputs.get("selector")
    wait_for = inputs.get("wait_for_selector")
    page.goto(url, timeout=30000)
    if wait_for:
        page.wait_for_selector(wait_for, timeout=15000)
    if selector:
        el = page.query_selector(selector)
        if not el:
            raise ValueError(f"Selector not found: {selector}")
        return {"text": el.inner_text()}
    return {"text": page.inner_text("body")}


def _action_fill_form(page: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    url = inputs.get("url", "about:blank")
    selector = inputs.get("selector", "")
    value = inputs.get("value", "")
    if not selector:
        raise ValueError("Selector required")
    page.goto(url, timeout=30000)
    el = page.query_selector(selector)
    if not el:
        raise ValueError(f"Selector not found: {selector}")
    el.fill(value)
    return {"filled": True}


def _action_click(page: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    url = inputs.get("url", "about:blank")
    selector = inputs.get("selector", "")
    if not selector:
        raise ValueError("Selector required")
    page.goto(url, timeout=30000)
    el = page.query_selector(selector)
    if not el:
        raise ValueError(f"Selector not found: {selector}")
    old_url = page.url
    el.click()
    wait_nav = inputs.get("wait_for_navigation", True)
    if wait_nav:
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
    return {"clicked": True, "navigated": page.url != old_url, "final_url": page.url}


def _action_wait_for_selector(page: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    selector = inputs.get("selector", "")
    state = inputs.get("state", "visible")
    timeout_ms = inputs.get("timeout_ms", 30000)
    if not selector:
        raise ValueError("Selector required")
    page.wait_for_selector(selector, state=state, timeout=timeout_ms)
    return {"found": True, "selector": selector, "state": state}


def _action_evaluate(page: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    expression = inputs.get("expression", "")
    if not expression:
        raise ValueError("Expression required")
    url = inputs.get("url")
    if url:
        page.goto(url, timeout=30000)
    result = page.evaluate(expression)
    return {"result": result}


def _run_ephemeral(action: str, inputs: dict[str, Any], headless: bool) -> dict[str, Any]:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless, args=["--no-sandbox"])
            try:
                page = browser.new_page()
                page.set_default_timeout(30000)
                result = _dispatch(action, page, inputs)
                return {"result": result}
            finally:
                browser.close()
    except PlaywrightTimeoutError:
        return {"error": {"code": "TIMEOUT", "message": "Browser operation timed out"}}
    except Exception as e:
        return _classify_error(e, action)


def _classify_error(e: Exception, action: str) -> dict[str, Any]:
    err_str = str(e).lower()
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    if isinstance(e, PlaywrightTimeoutError) or "timeout" in err_str:
        return {"error": {"code": "TIMEOUT", "message": str(e)}}
    if "selector" in err_str:
        return {"error": {"code": "SELECTOR_NOT_FOUND", "message": str(e)}}
    if "session" in err_str and ("not_found" in err_str or "missing" in err_str):
        return {"error": {"code": "SESSION_NOT_FOUND", "message": str(e)}}
    return {"error": {"code": "NAVIGATION_FAILED", "message": str(e)}}


def _with_artifact(result: dict[str, Any], path: Path, goal_id: str | None) -> dict[str, Any]:
    try:
        art = get_registry().add(path, produced_by="browser/run", goal_id=goal_id or "ad-hoc")
    except RegistryError:
        return result
    result["artifact_id"] = art.id
    result["artifact"] = {
        "id": art.id,
        "path": art.path,
        "kind": art.kind,
        "media_type": art.media_type,
        "size_bytes": art.size_bytes,
        "content_hash": art.content_hash,
    }
    return result


if __name__ == "__main__":
    import json
    import sys

    payload = json.loads(sys.stdin.read())
    print(json.dumps(run(payload)))
