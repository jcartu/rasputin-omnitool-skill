# PHASE-4 Gate Audit — Agent Loop

**Auditor:** Opus (claude-opus-4-7)
**Date:** 2026-05-09
**Skill repo HEAD:** `3a43866`
**Working tree:** clean
**Test suite:** 70 passed, 2 skipped (placeholders), 0 deprecation warnings

---

## Verdict: **REVISE**

Three rubric checks (4-7, 4-8, 4-9) FAIL outright and one (4-5) is PARTIAL. Together these gaps mean the agent loop has **never been exercised end-to-end** — neither against mocks (4-7) nor real tools (4-8), and tool-failure propagation through the reviewer is unverified (4-9). The PHASE-2 waiver does not extend here: that waiver covered scope merge of *already-implemented* code, whereas this is *missing* verification work explicitly enumerated by the brief (sub-tasks 4.4 and 4.5). The remaining work is ~115 min, well within a single re-audit round.

**Severity classification:**
- 4-7, 4-8, 4-9 → **BLOCKER**
- 4-5 → **IMPORTANT** (close to PASS but brief is explicit about "exactly" 2 examples for the analogous planner check)

---

## Rubric verification

### Independently verified by auditor

| Check | Evidence claim | Auditor finding | Status |
|---|---|---|---|
| 4-1 | `plan(goal, tools) -> Plan` typed dataclass | `agent/planner.py` 177 LOC; signature confirmed | ✅ PASS |
| 4-2 | 3 few-shot examples in `prompts/planner.md` | `grep` counts 3 example headers | ✅ PASS |
| 4-3 | `test_planner_only_uses_tools_in_catalog` | Test exists, mocks made-up tool then catalog tool | ✅ PASS |
| 4-4 | `execute(plan, tools) -> ExecutionTrace` + halt conditions | Confirmed in `agent/executor.py`; halt tests present | ✅ PASS |
| 4-5 | Executor prompt: one-tool-per-turn | Constraint present in prompt; **0 few-shot examples** vs brief's "2 few-shot examples" requirement | ⚠️ PARTIAL |
| 4-6 | Reviewer invokes Opus, parses to typed `Review` | `agent/reviewer.py` 118 LOC; 4 unit tests including malformed-response | ✅ PASS |
| 4-7 | Full loop end-to-end ≤2 min with mocked tools | `tests/loop_integration.py` exists but **both tests are `@pytest.mark.skip` with `NotImplementedError` body** — no actual loop has been run | ❌ FAIL |
| 4-8 | Full loop with real tools ≤5 min | Same skipped placeholder; `examples/run-demo.sh` does not exist; no `PHASE-4-demo-transcript.txt` in runlog | ❌ FAIL |
| 4-9 | Failure injection drives reviewer | `tests/test_failure_injection.py` does not exist | ❌ FAIL |
| 4-10 | Budget config respected (max-steps, failure rate, wallclock) | `test_max_steps_halt`, `test_failure_rate_halt` confirmed; cost ceiling not directly tested but config plumbing exists | ✅ PASS |
| 4-11 | Trace events written to `runlog/traces/` | 198 trace directories present (evidence undercount of 176 is non-blocking) | ✅ PASS |

### Universal checks

| Check | Auditor finding | Status |
|---|---|---|
| U-1 | `git status --short` empty | ✅ PASS |
| U-2 | `git log` shows 5 phase commits, all conventional, no `wip`/`tmp` | ✅ PASS |
| U-3 | No stray files outside workspace | ✅ PASS |
| U-4 | `pytest -W error::DeprecationWarning` returns 70 passed, 2 skipped | ✅ PASS |
| U-5 | No secrets/keys in diffs | ✅ PASS |
| U-6 | Verification phase, ETA tracking N/A | N/A |
| U-7 | 0 help requests | ✅ PASS |
| U-8 | All ✅ sub-tasks have commits | ✅ PASS |
| U-9 | No TODO markers in `agent/` or `tools/` | ✅ PASS |
| U-10 | Evidence file is well-formed Markdown with all required sections | ✅ PASS |

**Note on naming:** the integration test file is named `tests/loop_integration.py` (no `test_` prefix). Pytest still collects the two skipped functions because their function names start with `test_`, but the convention deviation is worth fixing during revision.

---

## Why this is REVISE, not APPROVE-WITH-WAIVER

The PHASE-2 waiver established a precedent for waiving *scope-merge* situations: tested, working code that was implemented in the wrong phase. The current gaps are categorically different:

1. **The work is missing, not misplaced.** Sub-tasks 4.4 and 4.5 in the brief specify deliverables (`test_failure_injection.py`, `test_loop_integration.py` with real test bodies, `examples/run-demo.sh`, demo transcript). None of these exist. There is no prior session implementation to retroactively gate.

2. **The missing checks are the highest-value ones.** 4-7/4-8/4-9 are the only checks that exercise the *integrated* loop. Without them, every individual component is unit-tested in isolation but the system is untested as a system. This is the exact failure mode the brief flagged in its "Why this phase exists" section: *"silent failure modes... mitigations: golden-task evals, schema validation, explicit halt conditions, **and a final integration test against real tools**."*

3. **The fix is small and well-scoped.** ~115 min of work is well within a single re-audit round (budget is 2). Waiving would discard a low-cost opportunity to close the system's most important verification gap.

4. **The skipped placeholders are misleading.** A reader of the test suite output sees "70 passed, 2 skipped" and reasonably infers integration coverage exists pending wire-up. The skip-reason `"wired in PHASE-4"` is now actively false post-PHASE-4 if these are not implemented.

---

## Required actions for re-audit

Address in this order. After completing, update `runlog/PHASE-4-evidence.md` and re-invoke audit.

1. **Implement `tests/test_failure_injection.py`** (~45 min) — the four tests enumerated in brief sub-task 4.4: tool-failure-propagates-to-review, planner-invalid-tool-caught, executor-malformed-tool-call-recovers, review-findings-drive-replan. Use mocked LLM clients consistent with existing `test_executor.py` patterns.

2. **Wire `tests/test_loop_integration.py`** (~45 min) — rename file to add `test_` prefix; replace the two `NotImplementedError` placeholders. The first (mocked tools, 4-7) should be deterministic and runnable in CI. The second (real tools, 4-8) can be marked `@pytest.mark.integration` and gated on `OPENCODE_ZEN_API_KEY` + `ANTHROPIC_API_KEY` env vars.

3. **Add `examples/run-demo.sh`** (~10 min) — exact script in brief sub-task 4.5 step 2; capture transcript to `runlog/PHASE-4-demo-transcript.txt`.

4. **Add 2 few-shot examples to `prompts/executor.md`** (~15 min) — one tool-call turn, one review-request turn, per brief sub-task 4.2 step 1.

**Effort estimate: Short (~115 min). One re-audit round consumed; one remaining.**

---

## Watch out for during revision

- **Don't write tautological integration tests.** The mocked-tool integration test (4-7) must drive at least one full plan → execute → review cycle and assert observable end-state (artifact files, review verdict, trace span count) — not merely that no exception was raised.
- **Real-tool test (4-8) must produce a real artifact.** The brief specifies "at least one `.md` artifact... contains 'Example Domain' or 'illustrative'". Don't substitute a softer assertion.
- **Failure injection must verify the reviewer *sees* the failure.** A test that confirms a tool errors but doesn't confirm the error reaches `Review.notes` would re-fail 4-9.

---

## Optional future considerations (out of scope for this gate)

- Cost ceiling halt (`COST_CEILING`) is plumbed but has no dedicated unit test. Brief check 4-10 says "with each budget set artificially low" — current tests cover MAX_STEPS and TOOL_FAILURE_RATE but not cost. Acceptable for this gate, worth a BACKLOG entry.
- The `loop_integration.py` filename should be normalized to `test_loop_integration.py` regardless; the current implicit collection by function-name prefix is fragile.

---

## Decision

**REVISE.** Re-audit after the four required actions above. Budget remaining: 1 round.
