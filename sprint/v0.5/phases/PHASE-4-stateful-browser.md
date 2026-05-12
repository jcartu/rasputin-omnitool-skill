# PHASE 4 — Stateful browser sessions

**Branch:** `sprint/v0.5-phase4`
**Estimated effort:** 4–5 hours
**Depends on:** Phase 3 approved

## Objective

Replace the single-shot Playwright tool with a session-aware browser. Cookies, localStorage, auth tokens, and (where possible) page state persist across tool calls. After this phase, the agent can log in once and operate within an authenticated context for the rest of the goal.

## Why

`tools/browser/index.py` today opens a fresh `chromium` browser inside every action — `launch()`, `new_page()`, do thing, close. Every login screen wins. Multi-step flows are impossible.

## Architecture

Mirror the sandbox-session pattern.

```python
@dataclass
class BrowserSession:
    session_id: str
    storage_state_path: Path        # JSON dump of cookies + localStorage
    user_data_dir: Path | None      # for chromium persistent context (preferred)
    created_at: datetime
    last_used_at: datetime
    last_url: str | None
```

Sessions live in `~/.rasputin/sessions/browser/<session_id>/`:
- `session.json`
- `storage_state.json` — Playwright's `storage_state` dump
- `user_data/` — chromium persistent context dir (full profile)
- `screenshots/` — saved screenshots tagged by session

### Persistence strategy

Playwright supports two patterns:

1. **`storage_state`** — JSON of cookies + origin storage. Portable, lightweight, but does NOT include service workers, IndexedDB, or open tabs.
2. **`launch_persistent_context(user_data_dir=...)`** — chromium user profile dir. Heavier but covers everything.

**Use (2) — `launch_persistent_context`.** It's strictly more powerful. The `user_data_dir` is the session's source of truth. We also dump `storage_state` after every action as a recovery snapshot.

### Lifecycle

1. **Provisioning.** First browser tool call with no `session_id` → manager creates a session, generates `user_data_dir`.
2. **Per-call browser spin-up.** For each tool call, launch a persistent context against the user_data_dir, run the action, then close the context. The user_data_dir persists; the live browser does not.
   - This is a deliberate trade-off: we lose per-action speed (each call pays cold-start) but gain robustness (zombie chromium processes are not our problem).
   - For high-frequency callers, Phase 4.5 (future) will add a session-pinned long-lived context.
3. **Storage state snapshot.** After each action, save `storage_state` to `storage_state.json`. This is the fallback if the user_data_dir gets corrupted.
4. **Eviction.** TTL + LRU as in Phase 3.

### Tool API changes

`tools/browser/index.py` actions all gain an optional `session_id` input. When absent, the tool auto-creates a session tied to `goal_id`.

New actions to add:
- `wait_for_selector` — useful for SPA flows. Inputs: `selector`, `state` (`attached`|`visible`|`hidden`|`detached`), `timeout_ms`.
- `evaluate` — run a JS expression and return the result. Inputs: `expression`. Output: `result`. Critical for scraping computed state.

Existing actions (`navigate`, `screenshot`, `extract_text`, `fill_form`, `click`) are extended:
- `screenshot` saves into the session's `screenshots/` dir; returns the path.
- `extract_text` accepts an optional `wait_for_selector` so SPAs that render late are handled.
- `click` accepts `wait_for_navigation: bool` (default True, current behaviour).

Note: the OpenAPI manifest must list all the new and changed inputs.

## Skeleton

See `skeletons/browser_session.py` for the manager class.

```python
class BrowserSessionManager:
    def __init__(self, root: Path, ...): ...
    def create(self, goal_id: str | None = None) -> BrowserSession: ...
    def attach(self, session_id: str) -> BrowserSession: ...
    def list(self, alive_only: bool = True) -> list[BrowserSession]: ...
    def evict(self, session_id: str) -> None: ...
    def garbage_collect(self) -> int: ...

    # convenience helpers used by the tool:
    def run_action(self, session: BrowserSession, fn: Callable[[Page], R]) -> R: ...
    # fn receives a Playwright Page bound to the session's persistent context;
    # the manager handles launching, running, snapshotting storage_state, closing.
```

## Files to change

```
A  agent/browser_session.py            # BrowserSessionManager
M  agent/session_manager.py            # add accessor for browser manager
M  tools/browser/index.py              # rewrite around sessions; new actions
M  tools/browser/manifest.json         # session_id, wait_for_selector, evaluate
M  agent/config.py                     # browser session TTL, max sessions, user_data_root
A  tests/test_browser_sessions.py
M  tests/test_browser.py               # update for session API; isolation tests
```

## Acceptance criteria

- `pytest -v tests/test_browser_sessions.py` passes (10+ test cases).
- Two-action flow works end-to-end: `navigate` to a page that sets a cookie, then `evaluate("document.cookie")` in the same session returns the cookie.
- Multi-action flow against a real site (use `https://httpbin.org/cookies/set?demo=v05` for reproducibility): set cookie via navigate, read via evaluate, screenshot — all under one session.
- Cross-session isolation: session A's cookie is invisible from session B.
- TTL eviction works.
- A goal can be run that requires login to a test site (use `https://httpbin.org/basic-auth/user/pass` with credentials in the goal); after auth via fill_form/click, subsequent calls in the session see the authenticated page.
- Screenshots land in the session's `screenshots/` dir and are returned as artifact paths.

## Unit-test scenarios that MUST exist

1. `create()` generates user_data_dir + writes session.json.
2. `attach()` succeeds on a live session; fails if user_data_dir is missing.
3. Two `navigate`+`evaluate` calls in the same session share cookies.
4. Cross-session isolation: cookie set in session A is not present in session B.
5. `storage_state.json` is written after each action (mtime check).
6. TTL eviction removes the user_data_dir from disk.
7. LRU eviction triggers at the cap.
8. `wait_for_selector` action: navigate to an HTML fixture with a delayed `<div>`, wait for it, then extract_text succeeds.
9. `evaluate` action: returns a JSON-serializable value; non-serializable returns are handled with an error.
10. `screenshot` writes into the session dir, path includes session_id.

## Self-verification

```bash
# Install Playwright browsers if not present (one-time)
python -m playwright install --with-deps chromium

pytest -v tests/test_browser_sessions.py 2>&1 | tee sprint/v0.5/phase-4-pytest.log

# Live cookie-persistence demo
python -c "
from agent.session_manager import get_browser_session_manager
from tools.browser.index import run as browser_run

mgr = get_browser_session_manager()
sess = mgr.create()
print('session:', sess.session_id)

r1 = browser_run({'action': 'navigate', 'url': 'https://httpbin.org/cookies/set?demo=v05', 'session_id': sess.session_id})
print('navigate:', r1)

r2 = browser_run({'action': 'evaluate', 'expression': 'document.cookie', 'url': 'https://httpbin.org/cookies', 'session_id': sess.session_id})
print('cookie:', r2)

assert 'demo=v05' in str(r2), 'cookie did not persist across actions'
print('OK — cookies survive across browser tool calls')
" 2>&1 | tee sprint/v0.5/phase-4-live-demo.log
```

## Phase evidence

In addition to the standard template:

- The cookie-persistence live demo output.
- A multi-step authenticated flow trace (login to httpbin basic-auth, then access protected URL).
- Disk-state confirmation: list `~/.rasputin/sessions/browser/` and show the session dirs.
- Cross-session isolation test output.

## Halt conditions specific to Phase 4

- If Playwright's `launch_persistent_context` is unstable on the host (chromium dying, profile lock contention), halt and consider a worker pool model where one chromium process owns multiple `BrowserContext` instances. Bigger refactor than this phase; do not improvise.
- If a target site uses anti-automation (Cloudflare interactive challenge) and we are tempted to add bot-bypass, STOP. Document and exclude such sites from the test suite; agent integrity matters more than that capability.

## Out of scope for Phase 4

- Headed mode toggling per session (default headless; user can override per call).
- Browser extensions, custom user agents, geolocation spoofing.
- Multi-tab management — one tab per session for v0.5.
- Network interception / mocking (Playwright supports it; not needed for v0.5).
- Devtools or trace capture beyond screenshots.
