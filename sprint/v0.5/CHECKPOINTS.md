# CHECKPOINTS — durable state protocol

## Why

Phase work spans hours. Power loss, OOM, network blip, or a reviewer ABORT must not destroy progress. Sisyphus must be resumable from a clean state file at any phase boundary, and from an intermediate commit within a phase.

## What is checkpointed

1. **Git commits.** Every phase has at least one terminal commit on its own branch `sprint/v0.5-phaseN`. Long phases (>90 min wall time or >200 LOC delta) require intermediate commits.
2. **State file.** `sprint/v0.5/state.json` is the single source of truth for "where are we." Updated atomically (`write to .tmp`, `rename`).
3. **Phase evidence.** `sprint/v0.5/phase-N-evidence.md` written before requesting Opus review.
4. **Review record.** `sprint/v0.5/review-N.json` written after Opus responds. Contains the full verdict payload.
5. **Halt records.** `sprint/v0.5/HALT-phase-N.md` written if a phase halts. Includes the failing test output, the last attempted patch, and a remediation hypothesis.

## state.json schema

```json
{
  "sprint": "v0.5",
  "started_at": "2026-05-12T18:00:00Z",
  "current_phase": 3,
  "phase_status": {
    "0": {"status": "approved", "review_count": 1, "commit": "abc1234"},
    "1": {"status": "approved", "review_count": 1, "commit": "def5678"},
    "2": {"status": "approved", "review_count": 2, "commit": "9876abc"},
    "3": {"status": "in_progress", "review_count": 0, "commit": null}
  },
  "halt_reason": null,
  "total_cost_usd": 4.27,
  "budget_usd": 25.00,
  "branches": {
    "0": "sprint/v0.5-phase0",
    "1": "sprint/v0.5-phase1",
    "2": "sprint/v0.5-phase2",
    "3": "sprint/v0.5-phase3"
  }
}
```

Valid statuses: `not_started`, `in_progress`, `awaiting_review`, `revise_requested`, `approved`, `halted`.

## Atomic update primitive

```python
# orchestration helper, do not inline edit state.json from shell
def update_state(updates: dict) -> None:
    p = Path("sprint/v0.5/state.json")
    state = json.loads(p.read_text())
    state.update(updates)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(p)
```

## Intermediate-commit rules for long phases

Apply to Phases 2, 3, 4, 5, 7. Every 90 minutes of wall time OR every 200 lines of net diff, whichever comes first:

```bash
git add -A
git commit -m "phase-N: WIP checkpoint $(date -u +%Y%m%dT%H%MZ) — <one-line what>"
git push origin sprint/v0.5-phaseN
```

Each intermediate commit MUST pass `ruff check .` even if tests are red. Lint failures at commit time signal sloppy work that the reviewer will catch.

## Resume protocol

On startup, every `run_phase.sh` invocation:

1. Reads `sprint/v0.5/state.json`.
2. If `current_phase == N` and `phase_status[N].status == "approved"`, advances to N+1 by re-invoking itself.
3. If `current_phase == N` and `phase_status[N].status == "halted"`, exits with code 78 and prints the halt path.
4. If `current_phase == N` and `phase_status[N].status == "awaiting_review"`, calls `review_with_opus.sh N` directly and does not re-run the phase work.
5. Otherwise, executes the phase brief.

## Recovery scenarios

| Failure | Recovery |
|---|---|
| Test failure after 2 patch attempts | Write `HALT-phase-N.md`, set `halted`, exit 78. |
| Opus review returns ABORT | Same as above. |
| Network failure to Anthropic API | Retry with backoff (1s, 4s, 16s). After third failure, exit 78 with `halt_reason: "anthropic_api_unreachable"`. Do NOT mark phase halted; Sisyphus can be re-launched after the network heals. |
| OOM during ReAct loop | Reduce executor context budget (env var) and re-run from last commit. |
| Process killed mid-phase | On next run, state shows `in_progress` with no halt. Sisyphus re-runs the phase from the last commit. Idempotency is enforced by each phase brief. |

## What is NOT checkpointed

- Sandbox container state. Each phase that needs sandboxes provisions them fresh from compose. Phase 3 changes this for runtime goals, but phase work itself does not depend on long-lived containers.
- Browser cookie jars in development. Phase 4 adds disk-backed `storage_state` for runtime sessions; during development the test fixtures use temp dirs.
- `outputs/` directory contents. These are generated artifacts of test runs and live outside git via `.gitignore`. The artifact registry in Phase 6 tracks them by hash for any deliverables that must be reproducible.

## State file invariants the reviewer checks

Each Opus review payload includes `state.json`. The reviewer will reject any phase where:

- The `current_phase` field does not match the phase being reviewed.
- `phase_status[N-1].status` is not `approved` (cannot skip phases).
- `total_cost_usd` is missing or stale.
- A `halt_reason` is set but `current_phase` is being advanced.
