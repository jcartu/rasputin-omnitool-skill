# PHASE 9 — Final review + release v0.5.0

**Branch:** `release/v0.5.0`
**Estimated effort:** 3–4 hours
**Depends on:** Phase 8 approved

## Objective

Merge all phase branches into `release/v0.5.0`, run the full acceptance suite end-to-end against real backends, submit the sprint to Opus for final review, address findings, and tag `v0.5.0`.

## Pre-merge checklist

Before merging:

- All 9 prior phases approved by Opus (state.json reflects this).
- `sprint/v0.5/state.json` shows zero halt records and total cost within budget.
- Every phase has its evidence file (`phase-N-evidence.md`).
- Every phase has its review record (`review-N.json`) with verdict APPROVE.
- Every phase has at least one pushed commit on its branch.

If any of the above fails, halt. Do not merge a sprint with gaps.

## Merge sequence

```bash
git checkout main
git pull origin main
git checkout -b release/v0.5.0

for N in 0 1 2 3 4 5 6 7 8; do
  echo "=== Merging sprint/v0.5-phase$N ==="
  git merge --no-ff "sprint/v0.5-phase$N" -m "Sprint v0.5 phase $N"
  # Run unit tests after each merge — catch interaction bugs early
  pytest -v 2>&1 | tee "sprint/v0.5/phase-${N}-postmerge-pytest.log"
  if [ $? -ne 0 ]; then
    echo "HALT: merge of phase $N broke tests"
    exit 78
  fi
done
```

If any merge breaks tests that were passing in isolation, halt and write `HALT-merge-N.md` with a diff diagnosis. Do not silently resolve.

## Acceptance suite

After successful merge, run `orchestration/final_review.sh`. This:

### 1. Lint and type-check

```bash
ruff check .
mypy agent/ tools/ --ignore-missing-imports
```

All clean.

### 2. Full unit suite

```bash
pytest -v 2>&1 | tee sprint/v0.5/final-unit.log
```

All tests pass. Test count is up significantly from v0.4 (target: ≥200 tests, up from 121).

### 3. e2e_smoke

```bash
# Requires: sandbox container up, RASPUTIN MCP at :8808, Playwright installed,
#           SearXNG up, ANTHROPIC_API_KEY and OPENCODE_ZEN_API_KEY set.
pytest -v tests/e2e_smoke.py 2>&1 | tee sprint/v0.5/final-e2e.log
```

Smoke tests are in this handover at `tests/e2e_smoke.py` — copy to project root.

### 4. Golden goals

```bash
python orchestration/run_golden_goals.py 2>&1 | tee sprint/v0.5/final-golden.log
```

The golden goals are defined in `tests/golden_goals.yaml`. Each is a real goal with explicit acceptance:
- Research goal (multi-source crawl + synthesis).
- Build goal (sandbox-driven code edit + test).
- Multimedia goal (image + audio + slides).
- Login goal (browser session with httpbin basic-auth).
- Resume goal (kill mid-flight, resume, complete).
- Wide goal (sub-agent fan-out).
- Streaming goal (event ordering correctness).

Every goal must complete with `verdict: APPROVE`. Cost must be within sprint budget.

### 5. Final Opus review

```bash
bash orchestration/final_review.sh
```

This packages all phase evidence + final test logs + golden-goal results into a single payload and submits to Opus with `rubrics/final-rubric.md`.

Opus returns APPROVE | REVISE | ABORT.

- **APPROVE** → tag `v0.5.0`, push the tag, write release notes.
- **REVISE** → address every finding, re-run final_review. One revise allowed.
- **ABORT** → halt, write `HALT-final.md`, wait for Joshua.

## Release notes — required content

Write `RELEASE-v0.5.0.md` with the following sections:

1. **Headline:** "First working release. v0.4 had a critical bug that prevented end-to-end goals from completing; v0.5 fixes that and adds five P0/P1 capabilities."

2. **What changed since v0.4:**
   - `load_tool_metadata()` returns real metadata (was empty list).
   - ReAct executor replaces static plan-walker (model in the loop).
   - Sandbox sessions: filesystem state survives across calls.
   - Browser sessions: cookies/auth survive across actions.
   - Checkpoint + resume: goals are durable.
   - Artifact registry: typed files with lineage and dedup.
   - Sub-agent tool: parallel fan-out replaces broken `wide_research`.
   - Streaming events: real per-step updates, not placeholders.

3. **Removed:**
   - `wide_research` (NameError, never worked).
   - `webapp_builder` (called a non-existent CLI).

4. **Fixed:**
   - `coding_agent` aider `--repo` flag (which doesn't exist).
   - `mail` dead temp-file write.
   - Pyproject fictitious dependencies (`voxtral-tts`, `openclaw-skill-sdk`, Python `promptfoo`).
   - Docker compose fabricated images.
   - `/home/josh/` default in Open WebUI valves.

5. **Breaking changes:**
   - Tool result shape: tools that produce files now return `artifact_id`. Old `path` field retained for one release.
   - `ExecutionTrace.artifacts` is now `list[str]` of IDs, not paths. Use `trace.artifact_paths()`.
   - Executor default mode is `react`. Fall back with `RASPUTIN_OMNITOOL_EXECUTOR_MODE=static`.

6. **Acceptance evidence:**
   - 200+ unit tests pass.
   - 7/7 golden goals pass.
   - End-to-end smoke green.
   - Opus final review: APPROVE.

7. **Known limitations:**
   - Parallel tool calls within a single ReAct turn not supported (planned next sprint).
   - Sub-agents cannot themselves spawn sub-agents (recursion is blocked).
   - No credential vault (env vars only; secrets redacted in event stream).
   - No persistent processes inside sandbox sessions (filesystem state only).

8. **Migration notes** for users of v0.4 — there are no v0.4 users in production by design, but document the path anyway.

## Files to change

```
M  pyproject.toml                       # version 0.5.0
M  manifest.json                        # version 0.5.0
M  README.md                            # tool count, capabilities summary
M  SKILL.md                             # update to v0.5 reality
A  RELEASE-v0.5.0.md
M  sprint/v0.5/state.json               # final state, all approved
```

## Acceptance criteria

- All steps 1–5 of the acceptance suite pass.
- Opus final review returns APPROVE.
- Tag `v0.5.0` pushed.
- Release notes written and committed.

## Self-verification

```bash
# Tag verification
git tag -l v0.5.0 | grep -q v0.5.0 || { echo "tag not created"; exit 1; }
git show v0.5.0 --quiet | head

# Version consistency
python -c "
import json
m = json.load(open('manifest.json'))
import tomllib  # python 3.11+
p = tomllib.loads(open('pyproject.toml').read())
assert m['version'] == p['project']['version'] == '0.5.0'
print('versions aligned: 0.5.0')
"

# Final manifest sanity
python -c "
import json
m = json.load(open('manifest.json'))
print('tools:', sorted(t['name'] for t in m['tools']))
print('count:', len(m['tools']))
"
# Expected: includes sub_agent; excludes wide_research, webapp_builder. Count ~16.
```

## Phase evidence

A `final-evidence.md` packaging everything:

- Pre-merge state.json snapshot.
- Per-phase test counts and approval reviews.
- Final acceptance suite results (1–5).
- Cost report: total sprint $ spent, breakdown by phase.
- Wall-clock breakdown: hours per phase, end-to-end sprint duration.
- Any halt/restart records during the sprint.
- The release notes.

## Halt conditions specific to Phase 9

- Merge conflicts between phase branches that cannot be resolved trivially → halt and ask for guidance. Do not invent merge resolutions.
- A golden goal that previously passed in isolation fails after merge → halt; this is exactly the integration bug we're here to catch.
- Final Opus review returns ABORT → halt, do not tag, write `HALT-final.md` with the verdict and a remediation plan.
- Cost overrun against sprint budget at this stage → tag anyway (work is done) but flag in the release notes for Joshua's attention.

## Out of scope for Phase 9

- Multi-version release engineering (LTS, deprecation policy).
- PyPI publishing (this is an in-repo OpenClaw skill; PyPI not relevant).
- Migration tooling from v0.4 (no production users).
- A changelog beyond `RELEASE-v0.5.0.md` (we can add a proper CHANGELOG.md in a future sprint).
