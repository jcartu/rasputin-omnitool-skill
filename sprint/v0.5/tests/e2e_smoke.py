"""tests/e2e_smoke.py — the canary.

Runs after every phase that touches the executor (≥2). Catches integration
regressions before they reach Opus.

Marked @pytest.mark.real_executor and @pytest.mark.skipif on missing
OPENCODE_ZEN_API_KEY so the suite is runnable without a key but the smoke
is actually exercised when the key is present.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest


pytestmark = pytest.mark.real_executor


SKIP_NO_KEY = pytest.mark.skipif(
    not os.environ.get("OPENCODE_ZEN_API_KEY") and not os.environ.get("RASPUTIN_OMNITOOL_EXECUTOR_ENDPOINT"),
    reason="no executor endpoint configured",
)


@SKIP_NO_KEY
def test_canary_crawl_and_summarize(tmp_path, monkeypatch):
    """The defining smoke: crawl example.com, produce a markdown summary."""
    monkeypatch.setenv("RASPUTIN_OMNITOOL_OUTPUTS_DIR", str(tmp_path))
    monkeypatch.setenv("RASPUTIN_OMNITOOL_MAX_COST_USD", "0.30")

    from agent import run_goal

    started = time.time()
    result = run_goal(
        "Crawl http://example.com and produce a 1-paragraph markdown summary saved to outputs/.",
        goal_id="e2e-canary",
    )
    elapsed = time.time() - started

    assert elapsed < 180, f"canary took {elapsed:.1f}s (cap 180)"
    assert result.get("review") is not None, "no review returned"
    verdict = result["review"].verdict
    assert verdict in ("APPROVE", "REVISE"), f"unexpected verdict: {verdict}"

    # At least one markdown artifact in outputs/
    mds = list(tmp_path.glob("*.md"))
    assert mds, f"no .md output in {tmp_path}"
    md_text = mds[0].read_text()
    assert "example" in md_text.lower(), "summary doesn't reference the crawled domain"


@SKIP_NO_KEY
def test_sandbox_session_persists(tmp_path, monkeypatch):
    """Two sandbox calls in the same goal share filesystem state.

    Skipped automatically if sandbox isn't reachable.
    """
    import httpx
    sandbox_url = os.environ.get("RASPUTIN_OMNITOOL_SANDBOX_URL", "http://localhost:8080")
    try:
        httpx.get(f"{sandbox_url}/v1/health", timeout=3).raise_for_status()
    except Exception:
        pytest.skip("sandbox not reachable")

    from agent.session_manager import get_sandbox_session_manager
    from tools.sandbox.index import run as sandbox_run

    mgr = get_sandbox_session_manager()
    sess = mgr.create(goal_id="e2e-session-test")

    r1 = sandbox_run({
        "operation": "code_execute",
        "code": "open('canary.txt', 'w').write('marker-12345')",
        "language": "python",
        "session_id": sess.session_id,
    })
    assert "result" in r1, f"first call failed: {r1}"

    r2 = sandbox_run({
        "operation": "code_execute",
        "code": "print(open('canary.txt').read())",
        "language": "python",
        "session_id": sess.session_id,
    })
    assert "result" in r2, f"second call failed: {r2}"
    assert "marker-12345" in r2["result"].get("stdout", ""), \
        "session state did not persist across calls"


@SKIP_NO_KEY
def test_browser_session_cookies(tmp_path):
    """Cookies survive across browser actions in one session."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("playwright not installed")
    try:
        from agent.browser_session import get_browser_session_manager
    except ImportError:
        pytest.skip("Phase 4 not yet implemented")
    from tools.browser.index import run as browser_run

    mgr = get_browser_session_manager()
    sess = mgr.create(goal_id="e2e-browser-test")

    r1 = browser_run({
        "action": "navigate",
        "url": "https://httpbin.org/cookies/set?demo=v05",
        "session_id": sess.session_id,
    })
    assert "result" in r1, f"navigate failed: {r1}"

    r2 = browser_run({
        "action": "evaluate",
        "expression": "document.cookie",
        "url": "https://httpbin.org/cookies",
        "session_id": sess.session_id,
    })
    assert "result" in r2, f"evaluate failed: {r2}"
    cookie_text = str(r2["result"].get("result", ""))
    assert "demo=v05" in cookie_text, f"cookie missing from response: {cookie_text}"
