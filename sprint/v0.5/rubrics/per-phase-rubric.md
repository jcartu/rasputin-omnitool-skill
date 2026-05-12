# Per-phase rubric

Opus grades each phase against this rubric. The reviewer system prompt at `prompts/reviewer-system.md` references this file.

## Evidence template

Every `phase-N-evidence.md` must include the following sections, in this order:

```markdown
# Phase N evidence — <one-line phase name>

## Summary
<2-3 sentence summary of what was done.>

## Files touched
<output of `git diff --stat sprint/v0.5..HEAD`>

## Acceptance criteria status
| # | Criterion | Status | Evidence path |
|---|---|---|---|
| 1 | <criterion text from phase brief> | PASS|FAIL|N/A | <log path> |
| ... | | | |

## Test results
- Unit tests: <pass count> passed, <fail count> failed, <skip count> skipped
- Integration tests (if applicable): <same>
- Coverage delta vs pre-phase: <+N% or N/A>

Paste the `pytest -v` tail (last 50 lines).

## Lint
- ruff: <clean | N errors>
- mypy: <clean | N errors in new files | unchanged in old files>

## Cost
- LLM cost this phase: $X.XX
- Sprint cost to date: $Y.YY
- Sprint budget: $25.00
- Headroom: $(25 - Y).YY

## Wall-clock
- Phase start: <ISO timestamp>
- Phase end: <ISO timestamp>
- Duration: <Hh Mm>

## Halt records (if any)
- <none | path to HALT-phase-N.md if a previous attempt halted>

## Out-of-spec changes
<Anything Sisyphus changed outside the phase brief's "Files to change" list, with justification. If none, write "None.">

## Open questions / risks for next phase
<Bullets. Empty list is fine; pretending there are none when there are is a finding.>
```

## Grading dimensions

Opus scores each phase on six dimensions. Each scored independently. Verdict comes from the worst score.

### 1. Goal completion

- **PASS** — every acceptance criterion in the phase brief is checked off with evidence (log path or test output).
- **PARTIAL** — most criteria PASS but ≥1 is missing or unclear.
- **FAIL** — any acceptance criterion is FAIL or not addressed.

### 2. Code quality

- **PASS** — new code is idiomatic, follows project conventions, no obvious code smells, lint clean.
- **PARTIAL** — minor concerns (naming, comments) but no functional problems.
- **FAIL** — copy-pasted bugs, dead code, swallowed exceptions, hardcoded magic numbers, leaks of personal paths or secrets.

### 3. Test quality

- **PASS** — tests cover the happy path AND at least one failure mode per public function added. Tests don't trivially pass (e.g. asserting `True`). Mocks are used only where backends are unavailable; real backends are tested where possible.
- **PARTIAL** — tests exist but coverage is thin in one area.
- **FAIL** — tests are mostly mock-vs-mock with no real-backend coverage where backends exist, OR tests assert nothing meaningful, OR new code has no tests.

### 4. Evidence honesty

- **PASS** — evidence accurately reflects state. Acceptance criteria status mirrors actual test outputs. Failures are surfaced, not hidden. "Out-of-spec changes" lists everything.
- **PARTIAL** — minor omission of a small change or a minor test result not mentioned.
- **FAIL** — evidence claims something works that doesn't. Halt records hidden. Acceptance ticked PASS for criteria that didn't actually pass. **This is treated as ABORT on first occurrence, no revise.**

### 5. Scope discipline

- **PASS** — Sisyphus stayed within the phase brief's "Files to change" list (plus any explicit "Out-of-spec changes" with justification).
- **PARTIAL** — incidental touches to adjacent files for trivial reasons (e.g. an import fix in a tool file while editing another). Acceptable if listed and justified.
- **FAIL** — Sisyphus added unrelated features, refactored adjacent code "while I was there," or jumped ahead to a future phase's work.

### 6. Reversibility and checkpoint hygiene

- **PASS** — at least one git commit per phase, more if the phase is long. The `state.json` is updated. Branch is pushed.
- **PARTIAL** — commit history is acceptable but state file or branch push lagged.
- **FAIL** — uncommitted changes, no checkpoints in a long phase, state file stale, missing intermediate commits in Phases 2/3/4/5/7.

## Verdict mapping

| Worst score across 6 dimensions | Verdict |
|---|---|
| All PASS | APPROVE |
| Any PARTIAL (and no FAIL) | REVISE |
| Any FAIL on dimensions 1, 2, 3, 5, or 6 | REVISE |
| FAIL on dimension 4 (evidence honesty) | ABORT |
| Two consecutive REVISE on the same phase | ABORT |

## REVISE handling

When Opus returns REVISE:

- Reviewer findings list specific actions ("add test for case X", "remove `/home/josh/` from line N of file Y", "the live demo log is missing").
- Sisyphus addresses ALL findings. Not "the important ones." All.
- Sisyphus re-writes `phase-N-evidence.md` to reflect the fixes (don't append a new section; rewrite the relevant rows).
- Sisyphus commits with message `phase-N: address review findings (round 2)` and re-invokes review.

## ABORT handling

When Opus returns ABORT, or when a second REVISE round still doesn't pass:

- Sisyphus writes `sprint/v0.5/HALT-phase-N.md` containing:
  - The full Opus verdict + findings.
  - The current state of the work (paste relevant diffs).
  - A proposed remediation plan.
  - Open question(s) Sisyphus cannot decide alone.
- `state.json.phase_status[N].status = "halted"`.
- Exit with code 78.
- Wait for Joshua's intervention.

Sisyphus does NOT roll back the work on ABORT. The branch and commits stay. Joshua needs to see what was attempted.
