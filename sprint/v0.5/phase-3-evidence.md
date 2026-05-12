# Phase 3 evidence — Persistent sandbox sessions

## Summary
Made sandbox state survive across multiple tool calls in the same goal. Implemented `SandboxSessionManager` with TTL and LRU eviction, updated the sandbox tool to accept optional `session_id`, and wired sessions through the ReAct executor. Sessions are filesystem-state only (no persistent processes).

## Files touched
Diff stat (sprint/v0.5-phase2..sprint/v0.5-phase3):
```
agent/config.py                      # added sandbox session config
agent/react_executor.py              # pass goal_id to tool calls
agent/session_manager.py             # NEW — SandboxSessionManager
manifest.json                        # regenerated
pyproject.toml                       # unchanged
tests/test_loop_integration.py       # unchanged
tests/test_sandbox.py                # updated to opt out of sessions
tests/test_sandbox_sessions.py       # NEW — 14 unit tests
tools/sandbox/index.py               # session_id support
tools/sandbox/manifest.json          # session_id input/output
```

## Counts
- Unit tests: 14 passed, 0 failed
- Full test suite: 155 passed, 6 skipped, 0 failed
- Pre-phase baseline (Phase 2): 141 passed, 6 skipped
- Delta: +14 tests (10 required + 4 helpers)
- Ruff: clean

## Acceptance criteria status
| # | Criterion | Status | Evidence path |
|---|-----------|--------|---------------|
| 1 | `pytest -v tests/test_sandbox_sessions.py` passes (10+ tests) | PASS | phase-3-pytest.log (14 tests) |
| 2 | Two sandbox calls share workspace | PASS | test_two_code_execute_calls_share_filesystem_state |
| 3 | Explicit session passing works | PASS | test_react_integration_two_sandbox_calls |
| 4 | TTL eviction works | PASS | test_ttl_eviction |
| 5 | LRU eviction works | PASS | test_lru_eviction |
| 6 | Killed container produces SESSION_DEAD | PASS | test_attach_fails_session_dead_when_container_gone |
| 7 | ReAct surfaces session_id in observation | PASS | test_react_integration_two_sandbox_calls |

## Test results
```
tests/test_sandbox_sessions.py::test_create_produces_ulid_and_writes_session_json PASSED
tests/test_sandbox_sessions.py::test_attach_succeeds_for_live_session PASSED
tests/test_sandbox_sessions.py::test_attach_fails_for_unknown_id PASSED
tests/test_sandbox_sessions.py::test_attach_fails_session_dead_when_container_gone PASSED
tests/test_sandbox_sessions.py::test_two_code_execute_calls_share_filesystem_state PASSED
tests/test_sandbox_sessions.py::test_filesystem_isolation_across_sessions PASSED
tests/test_sandbox_sessions.py::test_ttl_eviction PASSED
tests/test_sandbox_sessions.py::test_lru_eviction PASSED
tests/test_sandbox_sessions.py::test_explicit_evict_removes_session PASSED
tests/test_sandbox_sessions.py::test_list_alive_only_excludes_evicted PASSED
tests/test_sandbox_sessions.py::test_react_integration_two_sandbox_calls PASSED
tests/test_sandbox_sessions.py::test_ulid_format PASSED
tests/test_sandbox_sessions.py::test_is_alive_returns_false_for_unknown PASSED
tests/test_sandbox_sessions.py::test_schema_version_mismatch_raises PASSED
============================== 14 passed in 0.91s ==============================
```

Full suite: 155 passed, 6 skipped in 3.85s.

## Lint
- ruff: clean (All checks passed)

## Live demo
Cannot run live two-call demo (sandbox container not running). All session logic verified through mocked tests.

## Cost
- LLM cost this phase: $0.00
- Sprint cost to date: $2.24
- Sprint budget: $25.00
- Headroom: $22.76

## Wall-clock
- Phase start: 2026-05-12T09:30:00Z
- Phase end: 2026-05-12T10:00:00Z
- Duration: ~30m

## Halt records
- None

## Out-of-spec changes
- `manifest.json` — regenerated to sync with updated tool manifests (required after sandbox manifest changes).
- `agent/react_executor.py` — minor update to pass goal_id context to tool calls. Required for auto-session creation.
- `tests/test_sandbox.py` — updated to pass `session_id: None` to opt out of sessions where isolation is needed.

## Open questions / risks for next phase
- Phase 4 (Stateful browser sessions) follows a similar pattern to sandbox sessions.
- Live sandbox demo requires running sandbox container — cannot verify end-to-end without it.
