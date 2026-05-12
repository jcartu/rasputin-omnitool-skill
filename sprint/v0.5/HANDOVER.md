# v0.5 sprint — rasputin-omnitool-skill: from scaffold to working agent

**Target:** turn the broken v0.4 release into a real agent. Five P0/P1 priorities, executed across 10 phases, with Opus review at every phase gate and a final acceptance review.

**Executor:** Sisyphus running Qwen3.5-27B BF16 (local, OpenCode primary).
**Reviewer:** Claude Opus 4.7 via Anthropic API.
**Working branch:** `sprint/v0.5`.

---

## What we are fixing

From the v0.4 audit (see context):

1. **`load_tool_metadata()` returns `[]`.** Planner sees no tools, every plan fails validation. End-to-end is dead on tag.
2. **Executor is not an agent.** Static walker over a one-shot plan; no LLM in the loop; cannot recover or replan.
3. **No persistent sandbox sessions.** Every `sandbox` call hits a fresh container — filesystem state, deps, processes do not survive.
4. **Browser is single-shot.** Every action launches and tears down chromium. No cookies, no auth, no flows.
5. **No checkpoint/resume, no parallel sub-agents, no artifact registry, no streaming.**

Plus several broken or fictitious tools (`webapp_builder`, `wide_research` NameError, `coding_agent --repo` flag, `mail` dead code).

## Sprint structure

10 phases. Each phase has a brief in `phases/PHASE-N-*.md` with:
- Objective (one sentence)
- Files to change / create
- Acceptance criteria (testable)
- Skeleton code reference (if applicable, in `skeletons/`)
- Commands to run for self-verification
- Phase evidence requirements

| # | Phase | Branch checkpoint | Key skeleton |
|---|---|---|---|
| 0 | Truth pass (delete the lies) | `sprint/v0.5-phase0` | — |
| 1 | Tool metadata: fix planner catalog | `sprint/v0.5-phase1` | `tool_metadata.py` |
| 2 | ReAct executor (model in the loop) | `sprint/v0.5-phase2` | `react_executor.py` |
| 3 | Persistent sandbox sessions | `sprint/v0.5-phase3` | `session_manager.py` |
| 4 | Stateful browser sessions | `sprint/v0.5-phase4` | `browser_session.py` |
| 5 | Checkpoint + resume | `sprint/v0.5-phase5` | `checkpoint.py` |
| 6 | Artifact registry (typed files) | `sprint/v0.5-phase6` | `artifact_registry.py` |
| 7 | Sub-agent tool (parallel) | `sprint/v0.5-phase7` | `sub_agent_tool.py` |
| 8 | Streaming events to caller | `sprint/v0.5-phase8` | `event_stream.py` |
| 9 | Final review + release v0.5.0 | `release/v0.5.0` | — |

## Phase gate protocol — the review loop

Each phase ends with:

1. **Lint clean:** `ruff check . && mypy agent/ tools/` (allow current mypy noise; new code must be clean).
2. **Tests green:** `pytest -v` — all previously passing tests still pass + new tests added per phase brief pass.
3. **Phase evidence written:** `sprint/v0.5/phase-N-evidence.md` per the template in `rubrics/per-phase-rubric.md`.
4. **Commit + push** to `sprint/v0.5-phaseN` branch.
5. **Opus review** invoked via `orchestration/review_with_opus.sh N`.
6. Opus returns `APPROVE` | `REVISE` | `ABORT`:
   - `APPROVE` → merge to `sprint/v0.5`, advance to phase N+1.
   - `REVISE` → one revise loop allowed. Address every finding. Re-run review. If second review is also `REVISE`, treat as `ABORT`.
   - `ABORT` → halt. Write `sprint/v0.5/HALT-phase-N.md` with reviewer findings and proposed remedy. Wait for Joshua.

The full driver is `orchestration/run_phase.sh N`. It will not advance unless Opus approves.

## Checkpoint protocol

See `CHECKPOINTS.md` for full details. Short version:

- **Every phase = one branch + one push minimum.** No long-lived uncommitted work.
- **Inside long-running phases (2, 3, 4, 5, 7):** intermediate commits every 90 minutes or every 200 LOC, whichever first.
- **Test fixtures and runlog artifacts** are part of the commit. No "works on my machine."
- **State file** `sprint/v0.5/state.json` tracks current phase, last successful review, halt status. Read this on resume to know where Sisyphus is.

## Halt conditions

Sisyphus halts and writes `HALT-phase-N.md` (do not just stop silently) when any of:

- A test fails after two patch attempts inside a single phase.
- A required external tool (Playwright, sandbox HTTP, Anthropic API) is unreachable and cannot be made reachable.
- A schema or API contract for a real external service is unclear and a guess would risk silent corruption.
- Opus returns `ABORT` on a review.
- Two consecutive Opus reviews return `REVISE` for the same phase.
- The cost ceiling for the sprint (`RASPUTIN_OMNITOOL_SPRINT_BUDGET_USD`, default `25.00`) is exceeded.
- `RASPUTIN_OMNITOOL_SPRINT_HARD_STOP=1` is set in the env (manual override by Joshua).

When halted, Sisyphus does NOT delete the working branch and does NOT roll back. State is preserved exactly as it was at halt.

## Final acceptance

Phase 9 runs `orchestration/final_review.sh`. This:

1. Runs the full unit suite (must pass).
2. Runs `tests/e2e_smoke.py` against real local backends (sandbox container up, Playwright installed, RASPUTIN MCP at :8808, SearXNG at the configured URL).
3. Runs the golden goal suite in `tests/golden_goals.yaml` end-to-end.
4. Sends the full sprint evidence pack to Opus for final review using `rubrics/final-rubric.md`.
5. Opus must return `APPROVE` to tag `v0.5.0`.

If final review returns `REVISE`, Sisyphus addresses every finding and re-submits. One revise allowed. If second final review is not `APPROVE`, halt and write `HALT-final.md`.

## Files in this handover

```
v0.5-handover/
├── HANDOVER.md                 ← this file (entry point)
├── CHECKPOINTS.md              ← checkpoint protocol
├── orchestration/
│   ├── run_phase.sh            ← driver: run one phase end-to-end
│   ├── review_with_opus.sh     ← submit phase evidence to Opus
│   ├── opus_review.py          ← Anthropic API client for reviews
│   ├── halt_check.sh           ← health and halt detection
│   └── final_review.sh         ← end-of-sprint review
├── phases/
│   ├── PHASE-0-truth-pass.md
│   ├── PHASE-1-tool-metadata.md
│   ├── PHASE-2-react-executor.md
│   ├── PHASE-3-sandbox-sessions.md
│   ├── PHASE-4-stateful-browser.md
│   ├── PHASE-5-checkpoint.md
│   ├── PHASE-6-artifact-registry.md
│   ├── PHASE-7-sub-agent.md
│   ├── PHASE-8-streaming.md
│   └── PHASE-9-release.md
├── rubrics/
│   ├── per-phase-rubric.md     ← what Opus grades each phase against
│   └── final-rubric.md         ← what Opus grades the sprint against
├── prompts/
│   ├── reviewer-system.md      ← system prompt sent to Opus on every review
│   ├── executor-instructions.md← Sisyphus baseline behaviour for the sprint
│   └── halt-decision.md        ← prompt template for "should we halt" calls
├── skeletons/
│   ├── tool_metadata.py        ← Phase 1
│   ├── react_executor.py       ← Phase 2 (the big one — read carefully)
│   ├── session_manager.py      ← Phase 3
│   ├── browser_session.py      ← Phase 4
│   ├── checkpoint.py           ← Phase 5
│   ├── artifact_registry.py    ← Phase 6
│   ├── sub_agent_tool.py       ← Phase 7
│   └── event_stream.py         ← Phase 8
└── tests/
    ├── e2e_smoke.py            ← the canary; must pass at end of every phase ≥2
    ├── conftest_session.py     ← session fixtures
    └── golden_goals.yaml       ← acceptance suite for Phase 9
```

## Bootstrap commands

```bash
# In the rasputin-omnitool-skill repo root, on main:
git checkout -b sprint/v0.5
mkdir -p sprint/v0.5
unzip /path/to/v0.5-handover.zip -d sprint/v0.5/
cat sprint/v0.5/HANDOVER.md       # this file
cat sprint/v0.5/phases/PHASE-0-truth-pass.md
bash sprint/v0.5/orchestration/run_phase.sh 0
```

## Environment

Required:
- `ANTHROPIC_API_KEY` — for Opus reviews
- `OPENCODE_ZEN_API_KEY` (or your routed equivalent) — for planner/executor model
- `RASPUTIN_OMNITOOL_EXECUTOR_ENDPOINT` — local Qwen 27B endpoint
- `RASPUTIN_OMNITOOL_EXECUTOR_MODEL=qwen3.5-27b-bf16` (or your registered name)
- `RASPUTIN_OMNITOOL_REVIEWER_MODEL=claude-opus-4-7`

Optional but recommended:
- `RASPUTIN_OMNITOOL_SPRINT_BUDGET_USD=25.00`
- `LANGFUSE_*` — if Langfuse is up; otherwise traces go to disk only

## How to read this from Sisyphus

For an autonomous run:

```bash
for N in 0 1 2 3 4 5 6 7 8 9; do
  bash sprint/v0.5/orchestration/run_phase.sh "$N" || { echo "HALT at phase $N"; break; }
done
```

Each `run_phase.sh` is idempotent. If a phase halts and is later fixed, re-running advances correctly because the state file is the source of truth.
