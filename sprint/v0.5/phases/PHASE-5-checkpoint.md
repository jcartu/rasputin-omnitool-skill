# PHASE 5 — Checkpoint + resume

**Branch:** `sprint/v0.5-phase5`
**Estimated effort:** 4–6 hours
**Depends on:** Phase 4 approved

## Objective

Make goal execution durable. Periodic snapshots of {trace, messages, artifact registry pointers, session IDs} written to disk; `run_goal(resume_from=...)` re-attaches state and continues from the last snapshot.

## Why

Goals that run for hours (and Joshua's overnight sprints absolutely will) cannot tolerate a kernel panic, an OOM, or a `kill -9` evaporating two hours of work. Manus checkpoints aggressively. We must too.

## Architecture

### Checkpoint primitive

```python
@dataclass
class GoalCheckpoint:
    goal_id: str
    sprint_id: str | None
    goal_text: str
    step_count: int                     # number of executor steps completed
    cost_usd: float
    messages: list[dict]                # the ReAct conversation, full
    trace_steps: list[dict]             # ExecutionTrace.steps to date
    artifact_ids: list[str]             # IDs in the registry (Phase 6)
    sandbox_session_ids: list[str]
    browser_session_ids: list[str]
    created_at: datetime
    schema_version: int                 # bump on shape change
```

Stored at `~/.rasputin/checkpoints/<goal_id>/checkpoint-N.json`. Numeric N increments per snapshot. Latest pointer at `latest.json` (a small file with `{"latest": N}`).

### When to snapshot

- After every executor step (cheap; trace_steps grows by one).
- Before any model call that estimates `> $0.10` (expensive call; snapshot pre-call so we can resume if the call dies mid-stream).
- Manually via `checkpoint_now(reason="...")` callable, used by the reviewer or by external callers.

Snapshots are idempotent per `(goal_id, step_count)`. If a snapshot exists, it's overwritten (latest one wins) but always at the same N.

### Resume

`run_goal(resume_from=goal_id)`:
1. Loads `~/.rasputin/checkpoints/<goal_id>/latest.json`.
2. Loads checkpoint-N.json.
3. Verifies sandbox + browser session IDs are still alive; halts with `SESSIONS_EXPIRED` if any are dead.
4. Re-initializes the ReAct executor with the saved `messages` and continues from where it left off (the model sees the same conversation context as if it never died).
5. Returns the final result identically to a fresh `run_goal`.

If sessions are dead and the user explicitly wants to continue anyway, expose `resume_from=goal_id, allow_session_loss=True`. The agent loses sandbox filesystem and browser state but keeps the conversation. Use case: long research goals where state is mostly in artifacts already.

### Retention

- Default keep last 5 checkpoints per goal.
- `RASPUTIN_OMNITOOL_CHECKPOINT_KEEP=N` env var.
- Successful APPROVE'd goals: collapse to one final checkpoint (named `final.json`).
- Halted goals: keep ALL checkpoints, never collapse.

## Skeleton

See `skeletons/checkpoint.py`. Key entrypoints:

```python
def write_checkpoint(state: GoalCheckpoint) -> Path: ...
def load_checkpoint(goal_id: str, n: int | None = None) -> GoalCheckpoint: ...
def list_checkpoints(goal_id: str) -> list[int]: ...
def latest_checkpoint(goal_id: str) -> GoalCheckpoint | None: ...
def collapse_to_final(goal_id: str) -> None: ...
def garbage_collect(keep: int = 5) -> int: ...

def resume_goal(goal_id: str, allow_session_loss: bool = False) -> dict: ...  # the public API
```

`run_goal` is updated to call `write_checkpoint()` after each executor step.

## Files to change

```
A  agent/checkpoint.py                    # the checkpoint module
M  agent/__init__.py                      # run_goal accepts resume_from
M  agent/react_executor.py                # snapshot hook after each step
M  agent/config.py                        # CHECKPOINT_ROOT, CHECKPOINT_KEEP
M  agent/session_manager.py               # alive-check API for the resume path
A  tests/test_checkpoint.py
A  tests/test_resume.py                   # end-to-end resume against mocked LLM
```

## Acceptance criteria

- `pytest -v tests/test_checkpoint.py tests/test_resume.py` passes (15+ tests combined).
- Kill-mid-flight scenario: run a goal that issues 5 tool calls with a mocked LLM, kill the process after step 3, run `resume_goal(goal_id)`, verify the goal completes correctly and the artifacts end up correct.
- Snapshot frequency: confirm via test that a snapshot exists for every executor step.
- Schema versioning: corrupt or unknown schema version raises a clear `INCOMPATIBLE_CHECKPOINT` error, not a silent partial load.
- `garbage_collect()` retains the last N and `final.json`.
- Resume with `allow_session_loss=False` and dead sessions → clear `SESSIONS_EXPIRED` error.

## Unit-test scenarios that MUST exist

1. Write → read round-trip preserves all fields.
2. Latest pointer updates atomically (write to `.tmp` then rename).
3. Concurrent writes for the same `(goal_id, step_count)`: last write wins, no partial JSON.
4. `list_checkpoints()` returns numeric order.
5. `garbage_collect(keep=3)` deletes oldest, retains newest 3 + `final.json`.
6. `collapse_to_final()` removes intermediates, keeps `final.json`.
7. Schema version mismatch raises `INCOMPATIBLE_CHECKPOINT`.
8. Resume reconstructs the ReAct executor's `messages` correctly.
9. Resume with `allow_session_loss=False` + dead session_id → `SESSIONS_EXPIRED`.
10. Resume with `allow_session_loss=True` + dead session_id → succeeds; trace records the loss.

## Integration test scenario (in `test_resume.py`)

```python
def test_kill_and_resume(monkeypatch, tmp_path):
    monkeypatch.setenv("RASPUTIN_OMNITOOL_CHECKPOINT_ROOT", str(tmp_path / "ckpt"))

    # Phase 1: run partially.
    monkeypatch.setattr("agent.react_executor.call_model", make_fake_llm(steps=[
        {"tool_call": {"name": "crawl4ai", "args": {"url": "http://example.com"}}},
        {"tool_call": {"name": "deliverables", "args": {"title": "Test", "sections": [], "formats": ["md"]}}},
    ]))
    # Inject a fault after step 2:
    monkeypatch.setattr("agent.react_executor.MAX_STEPS_THIS_RUN", 2)

    res1 = run_goal("Test goal", goal_id="g-test-1")
    assert res1["halted"] is True
    assert res1["reason"] in ("MAX_STEPS", "INJECTED_FAULT")

    # Phase 2: resume; remove fault; expect completion.
    monkeypatch.setattr("agent.react_executor.MAX_STEPS_THIS_RUN", 10)
    monkeypatch.setattr("agent.react_executor.call_model", make_fake_llm(steps=[
        {"final": "Done. See outputs/report.md"},
    ]))

    res2 = resume_goal("g-test-1")
    assert res2["review"].verdict == "APPROVE"
    assert "report.md" in str(res2["artifacts"])
```

## Self-verification

```bash
pytest -v tests/test_checkpoint.py tests/test_resume.py 2>&1 | tee sprint/v0.5/phase-5-pytest.log

# Live demo: kill -9 and resume
python scripts/checkpoint_demo.py 2>&1 | tee sprint/v0.5/phase-5-live-demo.log
```

(Sisyphus must create `scripts/checkpoint_demo.py` as part of this phase. It runs a real goal under a child process, kills the child after N seconds, calls resume, prints the result.)

## Phase evidence

In addition to standard template:

- Test results for both unit and integration suites.
- The kill-and-resume live demo output.
- A directory listing of `~/.rasputin/checkpoints/<goal_id>/` from a completed run.
- The exact schema version shipped (number) and the migration plan for future bumps.

## Halt conditions specific to Phase 5

- If `messages` serialization is non-deterministic (e.g. some SDK objects don't round-trip JSON cleanly), halt and adopt a normalized message shape (dict-only, no SDK objects) before checkpointing. Resume that loses messages is worse than no resume.
- If atomic writes are not reliable on the target FS (e.g. older NFS), document and add an fsync step. Do not ship a checkpoint module with corruption windows.

## Out of scope for Phase 5

- Distributed checkpoints across machines.
- Compression of large message histories (Phase 8 streaming will help reduce them).
- Resume across schema versions (we ship v1; v2 design is for a future sprint).
- Encryption of checkpoint files. Joshua's `~/.rasputin/` is assumed local-trust; if that changes we'll add a vault.
