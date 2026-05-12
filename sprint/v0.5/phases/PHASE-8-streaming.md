# PHASE 8 — Streaming events to caller

**Branch:** `sprint/v0.5-phase8`
**Estimated effort:** 3–4 hours
**Depends on:** Phase 7 approved

## Objective

Add a real event stream from the executor to the caller. Open WebUI plugin (and any other surface) gets per-step status, tool call inputs/outputs, artifact additions, review verdicts, sub-agent progress — as they happen, not batched at the end.

## Why

Today the Open WebUI plugin claims to stream but actually emits two static placeholder messages around a blocking `run_goal()` call. The user stares at "Planning…" for a minute, then "Done" appears. Manus's polish comes substantially from live streaming; we must too.

## Architecture

### Event types

```python
@dataclass
class StreamEvent:
    type: str           # see below
    timestamp: datetime
    goal_id: str
    sub_agent_id: str | None
    data: dict
```

Type catalog (v0.5):

| `type` | When emitted | `data` fields |
|---|---|---|
| `goal.started` | once at run_goal start | goal_text |
| `goal.planning` | when planner kicks off (static mode) or react executor's first model call | model |
| `executor.step_started` | start of each ReAct step | step_index |
| `executor.model_call_started` | before each model call | model, est_tokens_in |
| `executor.model_call_completed` | after each model call | model, tokens_in, tokens_out, cost_usd, latency_s |
| `executor.tool_call_started` | before tool dispatch | tool_name, inputs (redacted) |
| `executor.tool_call_completed` | after tool dispatch | tool_name, status, output_preview, latency_s |
| `executor.artifact_added` | registry.add | artifact_id, kind, size_bytes, path |
| `executor.dedup_triggered` | duplicate tool call refused | tool_name, args_hash |
| `executor.session_created` | sandbox/browser session created | kind, session_id |
| `sub_agent.spawned` | per sub when sub_agent tool fires | sub_agent_id, sub_goal |
| `sub_agent.completed` | per sub | sub_agent_id, status, cost_usd |
| `checkpoint.written` | each snapshot | checkpoint_path, step_count |
| `reviewer.started` | reviewer dispatch | model |
| `reviewer.verdict` | reviewer returned | verdict, findings_count |
| `goal.completed` | once at run_goal end | verdict, artifacts, cost_usd, halted_for |
| `goal.halted` | only if halted | reason, last_checkpoint |

### Transport

The bus is an async-friendly queue. Two consumers:

1. **In-process callback** — `run_goal(on_event=callable)`. The callable is invoked synchronously per event. Used by tests.
2. **Async iterator** — `run_goal_streaming(...)` is an async generator yielding events. Used by Open WebUI plugin (which is an async coroutine).

The bus has no network/HTTP transport in v0.5. SSE/WebSocket can be added in a future sprint by wrapping the async iterator.

### Implementation

`agent/event_stream.py` provides:

```python
class EventBus:
    def emit(self, event: StreamEvent) -> None: ...
    def subscribe(self) -> AsyncIterator[StreamEvent]: ...
    def subscribe_sync(self, callback: Callable[[StreamEvent], None]) -> int: ...  # returns sub id
    def unsubscribe(self, sub_id: int) -> None: ...
```

There's a process-wide event bus exposed via `get_event_bus()`. Each `run_goal` creates a per-goal child bus that funnels into the parent. This lets multiple concurrent goals coexist without crosstalk.

### Redaction

`executor.tool_call_started.data.inputs` is auto-redacted: any field whose key matches `password|token|secret|api_key|auth` (case-insensitive) is replaced with `"***"`. Same for `model_call_started` if any messages contain such patterns. This is best-effort; the canonical place to manage secrets is a credential vault (future sprint).

### Backpressure

The async iterator uses an `asyncio.Queue` with a configurable max size (default 1000). On overflow, the OLDEST event is dropped (not the newest), so live tails remain coherent. A dropped-event counter is emitted as a special event when the queue empties.

### Open WebUI plugin update

`surfaces/open-webui/rasputin_function.py` uses the async iterator:

```python
async def run_goal(self, goal, __event_emitter__, ...):
    bus = get_event_bus().create_goal_stream(goal_id)
    task = asyncio.create_task(asyncio.to_thread(_run_goal, goal, goal_id=goal_id))
    async for event in bus:
        await __event_emitter__(_translate_event(event))
        if event.type in ("goal.completed", "goal.halted"):
            break
    return _format_final(await task)
```

Translate each `StreamEvent` to an Open WebUI status payload with appropriate descriptions.

## Skeleton

See `skeletons/event_stream.py` — full `EventBus` + `StreamEvent` + a sample subscriber.

## Files to change

```
A  agent/event_stream.py
M  agent/__init__.py                     # on_event callback support
M  agent/react_executor.py               # emit events at every step
M  agent/reviewer.py                     # emit verdict event
M  agent/checkpoint.py                   # emit checkpoint events
M  tools/sub_agent/index.py              # emit sub events
M  agent/artifact_registry.py            # emit artifact_added
M  surfaces/open-webui/rasputin_function.py
A  tests/test_event_stream.py
```

## Acceptance criteria

- `pytest -v tests/test_event_stream.py` passes (12+ tests).
- A run of the canary goal emits ALL expected event types in order; verifiable by collecting all events into a list and asserting type sequence.
- The Open WebUI plugin receives live events; manual test in Open WebUI shows status updates throughout a multi-step goal.
- Redaction works: an input field literally named `api_key` is `"***"` in the event but the underlying tool call sees the real value.
- Backpressure: a deliberate sleeping subscriber that ignores 2000 events does not deadlock the executor; oldest events are dropped; drop counter is correct.

## Unit-test scenarios that MUST exist

1. `subscribe_sync` callback fires for each emitted event in order.
2. Async `subscribe` yields events as they arrive.
3. Multiple subscribers all receive each event.
4. `unsubscribe` removes a subscriber cleanly.
5. Redaction: `password`/`api_key`/`token`/`secret`/`auth` fields are `"***"` in events.
6. Backpressure: slow consumer doesn't block fast producer; oldest events drop.
7. Drop counter event fires when queue empties after drops.
8. Per-goal child bus does not leak events to other goals.
9. Sub-agent events carry `sub_agent_id` and are attributable.
10. `goal.completed` is always the last event (or `goal.halted`).
11. Checkpoint events emit at the correct points (verified vs Phase 5 hooks).
12. Artifact events emit at registry adds (verified vs Phase 6 hooks).

## Self-verification

```bash
pytest -v tests/test_event_stream.py 2>&1 | tee sprint/v0.5/phase-8-pytest.log

# Live demo: collect events from a real run, print summary
python -c "
import asyncio
from agent import run_goal_streaming

async def go():
    events = []
    async for ev in run_goal_streaming('Crawl http://example.com and produce a 1-paragraph summary saved to outputs/.'):
        events.append(ev)
        print(f'{ev.timestamp.isoformat()}  {ev.type}')
    print(f'TOTAL: {len(events)} events')
    return events

asyncio.run(go())
" 2>&1 | tee sprint/v0.5/phase-8-live-demo.log
```

## Phase evidence

- The live-demo log showing full event stream.
- Manual screenshot or transcript from Open WebUI with live updates.
- Redaction confirmation: a synthetic event with `api_key` in inputs is shown redacted to the subscriber.
- Backpressure stress test output.

## Halt conditions specific to Phase 8

- If the Open WebUI event emitter API has changed and our translator doesn't fit, fall back to emitting plain text status messages for v0.5 rather than rewriting the plugin protocol. Document for a future sprint.
- If asyncio is incompatible with how Sisyphus's runtime invokes `run_goal` (we can't await in a sync context easily), expose only `subscribe_sync` and keep the streaming surface single-threaded for v0.5. Document the limitation.

## Out of scope for Phase 8

- Network transport (SSE, WebSocket).
- Event persistence to disk.
- Replay of past goals from the event log.
- A frontend other than Open WebUI.
- Filtering / subscriptions by event type at the bus level (subscribers filter client-side for v0.5).
