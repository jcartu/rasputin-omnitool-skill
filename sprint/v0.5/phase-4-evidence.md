# Phase 4 — Stateful Browser Sessions Evidence

## Acceptance Criteria

| # | Criteria | Status | Evidence |
|---|----------|--------|----------|
| 1 | `pytest -v tests/test_browser_sessions.py` passes (10+ tests) | PASS | 12 tests pass |
| 2 | Two-action cookie flow works end-to-end | PASS | Live demo below |
| 3 | Multi-action flow against httpbin.org/cookies | PASS | Live demo below |
| 4 | Cross-session isolation | PASS | `test_cross_session_isolation` |
| 5 | TTL eviction works | PASS | `test_ttl_eviction_removes_old_sessions` |
| 6 | Screenshots land in session dir | PASS | `test_screenshot_returns_path` |

## Live Demo Output

```
session: 1778577416351-b56235f19792a4e8
navigate: {'result': {'final_url': 'https://httpbin.org/cookies', 'title': '', 'status': 200, 'session_id': '1778577416351-b56235f19792a4e8'}}
cookie: {'result': {'result': 'demo=v05', 'session_id': '1778577416351-b56235f19792a4e8'}}
OK - cookies survive across browser tool calls
```

Full log: `sprint/v0.5/phase-4-live-demo.log`

## Test Results

```
$ pytest tests/test_browser_sessions.py tests/test_browser.py -v
22 passed in 1.47s

$ pytest tests/ -q
171 passed, 6 skipped in 10.97s
```

## Ruff

```
$ ruff check .
All checks passed!
```

## Files Changed

```
A  agent/browser_session.py            # BrowserSessionManager (254 lines)
M  tools/browser/index.py              # Session-aware rewrite with evaluate/wait_for_selector
M  tools/browser/manifest.json         # New actions, session_id input
M  agent/config.py                     # browser_session_root, TTL, max_sessions
A  tests/test_browser_sessions.py      # 12 unit tests
M  tests/test_browser.py               # Updated for session API + new action tests
M  manifest.json                       # Regenerated skill manifest
```

## Architecture Notes

- Uses `launch_persistent_context` with per-session `user_data_dir`
- Cookies restored via `context.add_cookies()` from saved `storage_state.json` (persistent context alone doesn't reliably persist session cookies across launches)
- Storage state snapshotted after each action as fallback
- TTL + LRU eviction mirrors sandbox session pattern

## Out-of-spec Changes

- Cookie restoration uses `context.add_cookies()` rather than `storage_state` kwarg (Playwright version doesn't support it on `launch_persistent_context`)
- The `run_action` method restores cookies from previous storage state before running the action
