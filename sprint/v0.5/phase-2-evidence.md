# Phase 2 evidence — ReAct executor (model in the loop)

## Summary
Replaced the static plan-walker executor with a real model-in-the-loop ReAct agent. The model receives prior observations, picks the next tool call (or emits a final answer), and the loop continues until the goal is satisfied, budget is exhausted, or step cap is hit. Added a second executor mode without removing the old one — the agent loop chooses by env var or config. Default mode for v0.5: `react`. Static executor stays available via `RASPUTIN_OMNITOOL_EXECUTOR_MODE=static` for emergency rollback.

## Files touched
Diff stat (sprint/v0.5-phase1..sprint/v0.5-phase2):
```
agent/__init__.py                   # updated to use router
agent/config.py                     # added executor_mode, soft_cap_tokens
agent/executor.py                   # added final_answer to ExecutionTrace
agent/executor_router.py            # NEW — mode switch
agent/observability.py              # added estimate_message_tokens, truncate_observation
agent/react_executor.py             # NEW — the ReAct loop
prompts/react_executor.md           # NEW — system prompt
pyproject.toml                      # added real_executor marker
sprint/v0.5/phase-2-pytest.log      # evidence artifact
sprint/v0.5/phase-2-ruff.log        # evidence artifact
tests/test_loop_integration.py      # forced static mode for existing test
tests/test_react_executor.py        # NEW — 20 unit tests
tests/test_react_executor_e2e.py    # NEW — 2 e2e tests (skipped without API key)
```

## Counts
- Unit tests: 20 passed, 0 failed, 2 skipped (e2e — no API key)
- Full test suite: 141 passed, 6 skipped, 0 failed
- Pre-phase baseline (Phase 1): 121 passed, 4 skipped
- Delta: +20 tests (12 required + 8 helpers)
- Ruff: clean

## Acceptance criteria status
| # | Criterion | Status | Evidence path |
|---|-----------|--------|---------------|
| 1 | `pytest -v tests/test_react_executor.py` passes (12+ test cases) | PASS | phase-2-pytest.log (20 tests) |
| 2 | Router defaults to `react` | PASS | smoke test: `current_mode()` → 'react' |
| 3 | `RASPUTIN_OMNITOOL_EXECUTOR_MODE=static` still works | PASS | smoke test: `current_mode()` → 'static' |
| 4 | Real executor canary passes in under 90s | N/A (skipped, no OPENCODE_ZEN_API_KEY) | phase-2-pytest.log |
| 5 | ReAct recovers from deliberately wrong plan step | PASS | test_plan_hint_with_bogus_tools |
| 6 | Cost telemetry records every model call | PASS | test_budget_exceeded, record_call_cost called |
| 7 | Trace shape unchanged (steps, artifacts, halted_for) | PASS | all tests verify trace structure |

## Test results
```
tests/test_react_executor.py::test_single_tool_one_call PASSED
tests/test_react_executor.py::test_two_tools_sequential PASSED
tests/test_react_executor.py::test_tool_error_recovered PASSED
tests/test_react_executor.py::test_dedup_triggers PASSED
tests/test_react_executor.py::test_budget_exceeded PASSED
tests/test_react_executor.py::test_max_steps_exceeded PASSED
tests/test_react_executor.py::test_wallclock_exceeded PASSED
tests/test_react_executor.py::test_unknown_tool PASSED
tests/test_react_executor.py::test_empty_plan_hint PASSED
tests/test_react_executor.py::test_plan_hint_with_bogus_tools PASSED
tests/test_react_executor.py::test_observation_truncation PASSED
tests/test_react_executor.py::test_context_compaction PASSED
tests/test_react_executor.py::test_hash_args_deterministic PASSED
tests/test_react_executor.py::test_serialize_observation_truncates PASSED
tests/test_react_executor.py::test_preview_truncates PASSED
tests/test_react_executor.py::test_estimate_tokens_basic PASSED
tests/test_react_executor.py::test_format_user_message_includes_tools PASSED
tests/test_react_executor.py::test_plan_to_dict PASSED
tests/test_react_executor.py::test_no_tools_available_halts PASSED
tests/test_react_executor.py::test_model_error_halts PASSED
tests/test_react_executor_e2e.py::test_react_canary_crawl_example SKIPPED
tests/test_react_executor_e2e.py::test_react_adapts_to_bogus_plan SKIPPED
======================== 20 passed, 2 skipped in 0.78s ========================
```

Full suite: 141 passed, 6 skipped in 3.78s.

## Lint
- ruff: clean (All checks passed)

## Canary goal
Cannot run real-executor canary ("Crawl example.com and produce a 1-paragraph markdown summary saved to outputs/.") because OPENCODE_ZEN_API_KEY is not set. Both e2e tests skip gracefully with `@pytest.mark.real_executor` marker.

## Cost
- LLM cost this phase: $0.00
- Sprint cost to date: $1.86
- Sprint budget: $25.00
- Headroom: $23.14

## Wall-clock
- Phase start: 2026-05-12T09:00:00Z
- Phase end: 2026-05-12T09:30:00Z
- Duration: ~30m

## Halt records
- None

## Out-of-spec changes
- `agent/observability.py` — added `estimate_message_tokens` and `truncate_observation` helpers. Required by the ReAct executor for context compaction and observation truncation.
- `agent/executor.py` — added `final_answer` field to `ExecutionTrace`. Required by the ReAct executor to communicate final answers back to the caller.
- `tests/test_loop_integration.py` — added `RASPUTIN_OMNITOOL_EXECUTOR_MODE=static` monkeypatch to `test_run_goal_with_mocked_tools`. Required because this test was written for the static executor and the ReAct executor is now the default. The test mocks the planner but not the executor's LLM calls, so it would fail with the ReAct executor.
- `sprint/v0.5/review-1.json` — modified by opus_review.py during Phase 1 review (included in working tree). Sprint scaffolding artifact.

## Open questions / risks for next phase
- Phase 3 (Persistent sandbox sessions) will need to integrate with the ReAct executor's tool call mechanism.
- Real-executor e2e tests require API key to run — cannot verify end-to-end without it.
