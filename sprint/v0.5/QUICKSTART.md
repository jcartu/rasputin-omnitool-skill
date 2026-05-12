# QUICKSTART — Sisyphus boot sequence

You are landing in this zip on day 1 of sprint v0.5. Do this in order.

## 1. Unpack into the project

From the rasputin-omnitool-skill repo root, on `main` (or whatever your default branch is):

```bash
git checkout -b sprint/v0.5
mkdir -p sprint/v0.5
unzip /path/to/v0.5-handover.zip -d sprint/v0.5/
git add sprint/v0.5
git commit -m "sprint v0.5: handover package landed"
git push -u origin sprint/v0.5
```

## 2. Read the entry points (in order)

1. `sprint/v0.5/HANDOVER.md` — the index
2. `sprint/v0.5/prompts/executor-instructions.md` — your operating principles
3. `sprint/v0.5/CHECKPOINTS.md` — checkpoint protocol
4. `sprint/v0.5/rubrics/per-phase-rubric.md` — how you will be graded

## 3. Environment

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export OPENCODE_ZEN_API_KEY=...                        # or your local routing
export RASPUTIN_OMNITOOL_EXECUTOR_ENDPOINT=http://localhost:8000/v1
export RASPUTIN_OMNITOOL_EXECUTOR_MODEL=qwen3.5-27b-bf16
export RASPUTIN_OMNITOOL_REVIEWER_MODEL=claude-opus-4-7
export RASPUTIN_OMNITOOL_SPRINT_BUDGET_USD=25.00
# Optional emergency brake (Joshua sets this manually):
# export RASPUTIN_OMNITOOL_SPRINT_HARD_STOP=1
```

## 4. Verify the environment is healthy

```bash
bash sprint/v0.5/orchestration/halt_check.sh
# Expect: OK: sprint healthy. spent $0 / $25.
```

## 5. Run phases one at a time

```bash
# Interactive (recommended for phase 0):
bash sprint/v0.5/orchestration/run_phase.sh 0

# After review APPROVES, continue:
bash sprint/v0.5/orchestration/run_phase.sh 1
# ...
```

## 6. Or run the whole sprint autonomously

```bash
for N in 0 1 2 3 4 5 6 7 8 9; do
  echo "=== Phase $N ==="
  RASPUTIN_OMNITOOL_NONINTERACTIVE=1 bash sprint/v0.5/orchestration/run_phase.sh "$N" || {
    echo "HALT at phase $N"; exit 1;
  }
done
```

When a phase returns 1 (REVISE), the outer loop above stops. The intent:
- Read `sprint/v0.5/review-N.json` for the findings.
- Address every finding.
- Re-run `bash sprint/v0.5/orchestration/run_phase.sh N`. It picks up where it left off.

When a phase returns 78 (ABORT / HALT), stop and wait for Joshua. The branch and commits stay.

## 7. End of sprint

Phase 9 runs `final_review.sh`. On APPROVE, `v0.5.0` is tagged and pushed.

## If you forget anything

The single source of truth is `sprint/v0.5/state.json`. Read it any time:

```bash
python3 sprint/v0.5/orchestration/state_helpers.py read
```

It tells you: current phase, what's approved, what's halted, total cost, remaining budget.
