# Final-sprint rubric

Opus grades the entire sprint at Phase 9 against this rubric. The reviewer system prompt is the same as for per-phase reviews; the rubric switch is in the payload.

## Final evidence template

`final-evidence.md`:

```markdown
# Sprint v0.5 — final evidence

## Headline
<one-line: "Sprint complete, all 7 golden goals pass, total cost $X.XX, duration Yh.">

## Phase-by-phase summary
| Phase | Status | Reviews | Cost | Duration |
|---|---|---|---|---|
| 0 | approved | 1 | $0.XX | Hh Mm |
| 1 | approved | 1 | $0.XX | Hh Mm |
| ... | | | | |
| 9 | <pending this review> | — | — | — |

## Cost
- Total LLM cost: $X.XX
- Budget: $25.00
- Headroom: $(25-X).XX

## Test counts
- v0.4 baseline: 121 tests
- v0.5 final: <N> tests
- Delta: +<M>
- Skipped: <K> (with reasons)

## Acceptance suite results
- Lint (`ruff check .`): <clean | N findings>
- Type-check (`mypy agent/ tools/`): <clean | N findings>
- Unit suite (`pytest -v`): <passed/failed/skipped>
- e2e_smoke (`pytest tests/e2e_smoke.py`): <passed/failed/skipped>
- Golden goals: <K of 7 passed>

## Golden goals breakdown
| Goal | Verdict | Cost | Wall-clock | Artifacts |
|---|---|---|---|---|
| research | APPROVE | $0.XX | Mm Ss | <N> |
| build | APPROVE | $0.XX | Mm Ss | <N> |
| multimedia | APPROVE | $0.XX | Mm Ss | <N> |
| login | APPROVE | $0.XX | Mm Ss | <N> |
| resume | APPROVE | $0.XX | Mm Ss | <N> |
| wide | APPROVE | $0.XX | Mm Ss | <N> |
| streaming | APPROVE | $0.XX | Mm Ss | <N> |

## Halt records during sprint
<list each HALT-*.md with timestamp and resolution. Empty list is ideal.>

## Architectural deltas
For each of the five P0/P1 priorities, one sentence on what was actually built:
- P0-1 load_tool_metadata: ...
- P0-2 ReAct executor: ...
- P0-3 Sandbox sessions: ...
- P0-4 Browser sessions: ...
- P1 checkpoint + artifact registry + sub-agent + streaming: ...

## Honest gaps
What didn't get done that you wish had. Spell it out. The reviewer will catch padding here.

## Migration / backwards compatibility
What v0.5 changes that any user (including Joshua) needs to know.

## Recommended next sprint
3–5 bullets on the highest-leverage next moves. Not required to be done, but the sprint that ends without recommendations is incomplete.
```

## Grading dimensions for final review

### 1. End-to-end correctness

- **PASS** — every golden goal returns APPROVE. The e2e_smoke passes. The acceptance suite is green.
- **PARTIAL** — 5–6 of 7 golden goals pass; the failures have clear, narrow, documented causes.
- **FAIL** — fewer than 5 golden goals pass, OR any failure is in a primitive added by P0 work (executor, sessions, checkpoint).

### 2. Architectural completeness

- **PASS** — all five P0/P1 priorities are real (not stubbed; not "partial implementation behind a flag"). The ReAct executor is the default. Sessions persist. Checkpoints survive a kill -9. Artifact registry works. Sub-agents parallelize.
- **PARTIAL** — one priority is implemented but limited (e.g. checkpoint works but only at coarse granularity).
- **FAIL** — any priority is mocked, simulated, or behind a "future work" flag.

### 3. Hygiene

- **PASS** — no fake dependencies in pyproject.toml. No fabricated docker images. No `/home/josh/` defaults. Lint and type-check are clean for new code. README and SKILL.md reflect reality. Manifest tool count matches what ships.
- **PARTIAL** — one or two minor inconsistencies.
- **FAIL** — any of the v0.4 truth-issues survives into v0.5.

### 4. Test quality

- **PASS** — total tests up significantly. Real-backend integration tests exist for sandbox, browser, executor. Mocks used only where unavoidable. Skip count is small and justified.
- **PARTIAL** — mostly real tests but one major area (e.g. browser) still mock-only.
- **FAIL** — bulk of new tests are mock-vs-mock, OR the previously-skipped real-tools end-to-end test (`test_run_goal_research_simple` style) is still skipped.

### 5. Evidence honesty

- **PASS** — final evidence accurately reflects state. Honest gaps section is non-empty (no sprint is perfect). Halt records, if any, are documented.
- **PARTIAL** — minor omissions.
- **FAIL** — claims of completeness that aren't backed by tests; missing halt records; cost numbers that don't reconcile.

### 6. Migration path

- **PASS** — release notes clearly document breaking changes. Backwards-compat fallbacks exist for one release (static executor; legacy artifact path field).
- **PARTIAL** — release notes mention changes but skip migration guidance.
- **FAIL** — breaking changes are undocumented; no fallback exists for the executor mode.

## Verdict mapping

| Worst score | Verdict |
|---|---|
| All PASS | APPROVE → tag v0.5.0 |
| Any PARTIAL with no FAIL | REVISE → one revise round |
| Any FAIL on dimensions 1, 2, 4, 5, 6 | REVISE → one revise round |
| FAIL on dimension 5 (evidence honesty) | ABORT immediately |
| Two consecutive REVISE on final | ABORT |

## After APPROVE

Sisyphus performs:

```bash
git checkout release/v0.5.0
git tag -a v0.5.0 -m "Sprint v0.5: first working release (ReAct + sessions + checkpoint + artifacts + sub-agents + streaming)"
git push origin release/v0.5.0
git push origin v0.5.0

# Update main:
git checkout main
git merge --ff-only release/v0.5.0
git push origin main
```

And writes the final entry to state.json:

```json
{
  "current_phase": 9,
  "phase_status": {
    "9": {"status": "approved", "review_count": <N>, "commit": "<sha>"}
  },
  "sprint_complete": true,
  "completed_at": "<ISO timestamp>",
  "released_tag": "v0.5.0"
}
```
