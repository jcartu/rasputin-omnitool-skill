"""tools/browser/index.py — Operate a browser via Playwright sync API.

Inputs: action, url, selector, value, headless
Outputs: result
Errors: NAVIGATION_FAILED, SELECTOR_NOT_FOUND, TIMEOUT

Status: WIRED (PHASE-3). Direct Playwright sync API (Option A).
"""
from __future__ import annotations
from pathlib import Path
from typing import Any

from agent.config import CONFIG


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    action = inputs.get("action", "")
    if action not in ("navigate", "screenshot", "extract_text", "fill_form", "click"):
        return {"error": {"code": "INVALID_OPERATION", "message": f"Unknown action: {action}"}}

    headless = inputs.get("headless", True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"error": {"code": "NAVIGATION_FAILED", "message": "Playwright not installed"}}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless, args=["--no-sandbox"])
            page = browser.new_page()
            page.set_default_timeout(30000)

            if action == "navigate":
                url = inputs.get("url", "")
                if not url:
                    return {"error": {"code": "NAVIGATION_FAILED", "message": "URL required"}}
                try:
                    response = page.goto(url, timeout=30000)
                    return {
                        "result": {
                            "final_url": page.url,
                            "title": page.title(),
                            "status": response.status if response else None,
                        }
                    }
                except Exception as e:
                    return {"error": {"code": "NAVIGATION_FAILED", "message": str(e)}}

            elif action == "screenshot":
                url = inputs.get("url", "about:blank")
                page.goto(url, timeout=30000)
                screenshots_dir = Path(CONFIG.outputs_dir) / "browser-screenshots"
                screenshots_dir.mkdir(parents=True, exist_ok=True)
                path = screenshots_dir / f"screenshot_{len(list(screenshots_dir.glob('*.png')))+1}.png"
                page.screenshot(path=str(path))
                return {"result": {"path": str(path)}}

            elif action == "extract_text":
                url = inputs.get("url", "about:blank")
                selector = inputs.get("selector")
                page.goto(url, timeout=30000)
                if selector:
                    el = page.query_selector(selector)
                    if not el:
                        return {"error": {"code": "SELECTOR_NOT_FOUND", "message": f"Selector not found: {selector}"}}
                    return {"result": {"text": el.inner_text()}}
                return {"result": {"text": page.inner_text("body")}}

            elif action == "fill_form":
                url = inputs.get("url", "about:blank")
                selector = inputs.get("selector", "")
                value = inputs.get("value", "")
                if not selector:
                    return {"error": {"code": "SELECTOR_NOT_FOUND", "message": "Selector required"}}
                page.goto(url, timeout=30000)
                el = page.query_selector(selector)
                if not el:
                    return {"error": {"code": "SELECTOR_NOT_FOUND", "message": f"Selector not found: {selector}"}}
                el.fill(value)
                return {"result": {"filled": True}}

            elif action == "click":
                url = inputs.get("url", "about:blank")
                selector = inputs.get("selector", "")
                if not selector:
                    return {"error": {"code": "SELECTOR_NOT_FOUND", "message": "Selector required"}}
                page.goto(url, timeout=30000)
                el = page.query_selector(selector)
                if not el:
                    return {"error": {"code": "SELECTOR_NOT_FOUND", "message": f"Selector not found: {selector}"}}
                old_url = page.url
                el.click()
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
                return {"result": {"clicked": True, "navigated": page.url != old_url}}

            browser.close()
    except TimeoutError:
        return {"error": {"code": "TIMEOUT", "message": "Browser operation timed out"}}
    except Exception as e:
        err_str = str(e).lower()
        if "selector" in err_str:
            return {"error": {"code": "SELECTOR_NOT_FOUND", "message": str(e)}}
        return {"error": {"code": "NAVIGATION_FAILED", "message": str(e)}}


if __name__ == "__main__":
    import json, sys
    payload = json.loads(sys.stdin.read())
    print(json.dumps(run(payload)))
