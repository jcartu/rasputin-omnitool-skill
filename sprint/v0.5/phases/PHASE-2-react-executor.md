# PHASE 2 — ReAct executor (model in the loop)

**Branch:** `sprint/v0.5-phase2`
**Estimated effort:** 6–10 hours (the biggest phase by far)
**Depends on:** Phase 1 approved

## Objective

Replace the static plan-walker with a real agent loop. The model receives prior observations, picks the next tool call (or emits a final answer), and the loop continues until the goal is satisfied, budget is exhausted, or step cap is hit. This is the single biggest architectural change in the sprint.

## Why this matters

The current `agent/executor.py` is a `for task in plan.tasks:` loop with `${T1.key}` string substitution. No LLM in the loop. No replanning. No adaptation. No recovery. Manus's defining capability is *adaptive execution*. Without this phase, every other phase is incremental polish on the wrong shape.

## Architecture

We add a second executor mode without removing the old one. The agent loop chooses by env var or config.

```
agent/
├── executor.py             # existing — keep for fallback / regression
├── react_executor.py       # NEW — the model-in-the-loop agent
└── executor_router.py      # NEW — picks one based on config
```

Both executors take the same inputs (`Plan`, `tools: dict[str, Callable]`) and return the same `ExecutionTrace`. The reviewer does not change.

Default mode for v0.5: `react`. The static executor stays available via `RASPUTIN_OMNITOOL_EXECUTOR_MODE=static` for emergency rollback.

Note: ReAct does not need the planner's full DAG — it adapts as it goes. But we keep the planner's plan as **initial guidance** (the planner output is fed in as a `system` message hint, not as a hard schedule). Planner output goes from "the schedule" to "advice." This is the right shape for v0.5.

## The skeleton

Read `skeletons/react_executor.py` carefully. It contains the full reference implementation: OpenAI-compatible function-calling, observation truncation, budget enforcement, dedup of repeated calls, and a final-answer detection path. Sisyphus should port it to the project, not retype it from scratch.

Key shape:

```python
def react_execute(
    goal: str,
    tools: dict[str, ToolDefinition],
    tool_metadata: list[dict],
    plan_hint: Plan | None,
    max_steps: int = 30,
    budget_usd: float = 0.50,
    max_wallclock_min: int = 20,
) -> ExecutionTrace:
    messages = [
        {"role": "system", "content": REACT_SYSTEM_PROMPT},
        {"role": "user", "content": format_goal_and_hint(goal, plan_hint, tool_metadata)},
    ]
    tool_schemas = [to_openai_tool_schema(t) for t in tool_metadata]

    trace = ExecutionTrace(plan=plan_hint or Plan(goal=goal, tasks=[]))
    halted = False
    for step in range(max_steps):
        if check_halt_conditions(trace, budget_usd, max_wallclock_min, started_at):
            trace.halted_for = "..."  # see skeleton for exact reason
            break

        response = call_model(messages, tool_schemas, model=CONFIG.executor_model)
        record_call_cost(...)

        if response.choices[0].finish_reason == "stop":
            # Model emitted final text; we are done.
            trace.final_answer = response.choices[0].message.content
            break

        tool_calls = response.choices[0].message.tool_calls or []
        if not tool_calls:
            # Model emitted text without a tool call. Could be a final answer or confusion.
            trace.final_answer = response.choices[0].message.content
            break

        # Append the assistant turn (with tool calls) before the tool responses.
        messages.append(response.choices[0].message.model_dump(exclude_unset=True))

        for tc in tool_calls:
            tool_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}

            if dedup_loop_detected(trace, tool_name, args):
                # Refuse to repeat the same call; tell the model.
                obs = {"error": "DUPLICATE_TOOL_CALL", "message": "Same tool+args used recently; pick a different approach."}
            elif tool_name not in tools:
                obs = {"error": "UNKNOWN_TOOL", "message": f"Tool '{tool_name}' is not available."}
            else:
                try:
                    obs = tools[tool_name](args)
                except Exception as e:
                    obs = {"error": "TOOL_EXCEPTION", "message": str(e)}

            trace.steps.append(...)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": serialize_observation(obs, max_chars=8000),
            })

        # Context window management.
        messages = compact_messages_if_oversize(messages, soft_cap_tokens=18_000)

    return trace
```

## Critical implementation details

1. **Tool schemas in OpenAI format.** Every tool's `inputs` dict gets converted to a JSON Schema `parameters` block. The skeleton has `to_openai_tool_schema()`. Bad schemas are the #1 source of model confusion.

2. **Observation truncation.** Tool outputs can be enormous (a crawl, a sandbox stdout). Truncate to a configurable per-tool cap (`max_observation_chars`, default 8000) and surface a "truncated" marker. Keep the full output in the trace; the model only sees the truncation.

3. **Dedup heuristic.** If the same `(tool_name, args)` tuple has been called in the last 3 steps and produced an error, refuse the call and respond with `DUPLICATE_TOOL_CALL`. Prevents infinite loops on the same broken call.

4. **Budget gate before every model call** (not just before tool calls). Use the existing `check_cost_ceiling` from `agent/observability.py`.

5. **Wall-clock gate.** Already exists in static executor; port it.

6. **Final-answer detection.** Two signals: `finish_reason == "stop"`, OR a model message with no tool_calls. Both are valid termination.

7. **Cost telemetry.** Call `record_call_cost` after every model call. The skeleton does this; do not strip it.

8. **System prompt for ReAct.** Write `prompts/react_executor.md`. Content described below.

9. **Compact mode.** When messages exceed `soft_cap_tokens`, drop or summarize older tool observations. Skeleton has a simple sliding-window approach. Do NOT drop the system or original user message.

## prompts/react_executor.md

```markdown
# ReAct executor system prompt

You are the executor for rasputin-omnitool-skill. You receive a user goal and a set of tools you can call. You operate one step at a time:

1. Think about what needs to happen next.
2. Either call exactly one tool, or emit a final answer if the goal is complete.
3. Inspect the tool result the next turn and decide again.

## Rules

- Use only tools listed in your tool schema. Do not invent tools.
- Prefer cheap deterministic tools (web_search, crawl4ai, sandbox) before expensive ones (image_gen, video_gen).
- Stop and emit a final answer once the goal is satisfied. Do not call tools "to be thorough" once the work is done.
- If a tool fails twice with the same inputs, try a different tool or a different approach. Do not retry the same exact call a third time.
- Surface tool errors clearly in your reasoning; do not hide them.
- For research goals, always include source URLs in the final answer.
- For file-producing goals, the final answer must reference the artifact path(s) the tools returned.

## Planner hint

You may receive a `plan_hint` field with a suggested sequence of steps. Treat it as advice from a planner. Deviate when the situation changes — for example, when an early tool result invalidates a later planned step. Do not blindly follow the hint.

## Termination

Emit a final answer (no tool call) when:
- All success criteria from the goal are met, OR
- You cannot make further progress and have a clear explanation why, OR
- The user goal is impossible with the available tools (state this plainly).
```

## Files to change

```
A  agent/react_executor.py              # the loop
A  agent/executor_router.py             # mode switch
M  agent/__init__.py                    # use router
A  prompts/react_executor.md            # system prompt
M  agent/observability.py               # add helpers used by ReAct (token-estimate, observation-truncate)
A  tests/test_react_executor.py         # unit tests w/ mocked LLM
A  tests/test_react_executor_e2e.py     # @pytest.mark.real_executor, requires API key
M  agent/config.py                      # RASPUTIN_OMNITOOL_EXECUTOR_MODE, soft_cap_tokens
```

## Acceptance criteria

- `RASPUTIN_OMNITOOL_EXECUTOR_MODE=react pytest -v tests/test_react_executor.py` passes (12+ test cases minimum).
- The router defaults to `react`.
- Setting `RASPUTIN_OMNITOOL_EXECUTOR_MODE=static` still produces a working static executor (regression).
- Real executor test (`-m real_executor`) passes the canary goal "Crawl example.com and produce a 1-paragraph markdown summary saved to outputs/." in under 90 seconds.
- The same canary goal succeeds with the new executor even when the planner's plan has a deliberately wrong step (test fixture: planner emits a bogus `tts` call at step 2; ReAct must skip or adapt).
- Cost telemetry: every model call records cost; goal halts cleanly at the configured budget.
- Trace shape unchanged: `ExecutionTrace.steps`, `.artifacts`, `.halted_for` populated correctly. Reviewer reads it identically.

## Unit-test scenarios that MUST exist

1. **Single tool, one call.** Mock LLM emits one tool_call then a stop. Trace has one step, final answer present.
2. **Two tools, sequential.** Mock LLM emits crawl, observes, then deliverables, then stop. Trace has two steps.
3. **Tool error recovered.** Mock LLM emits broken call, observes error, picks different tool, succeeds.
4. **Dedup triggers.** Mock LLM emits same (name, args) three times; third gets DUPLICATE_TOOL_CALL.
5. **Budget exceeded.** Set `budget_usd=0.001`; loop halts with `BUDGET` after the first paid call.
6. **Max steps exceeded.** Set `max_steps=2`; loop halts with `MAX_STEPS`.
7. **Wall-clock exceeded.** Mock a slow LLM (`time.sleep` patch); halts with `WALLCLOCK`.
8. **Unknown tool.** Mock LLM calls `bogus_tool`; gets UNKNOWN_TOOL observation, then resolves.
9. **Empty plan_hint works.** Pass `plan_hint=None`; executor runs from goal alone.
10. **Plan_hint with bogus tools.** Pass a plan whose tools don't exist; ReAct adapts.
11. **Observation truncation.** Tool returns 50 KB string; observation in messages is ≤8KB; full output preserved in `trace.steps`.
12. **Context compaction.** Drive enough steps that the soft cap triggers; verify oldest tool turns are dropped but system+user persist.

## Self-verification

```bash
pytest -v tests/test_react_executor.py 2>&1 | tee sprint/v0.5/phase-2-pytest.log

# Real-executor canary (requires endpoint + key):
if [ -n "$OPENCODE_ZEN_API_KEY" ]; then
  RASPUTIN_OMNITOOL_EXECUTOR_MODE=react pytest -v -m real_executor tests/test_react_executor_e2e.py 2>&1 | tee sprint/v0.5/phase-2-real.log
fi

# Confirm router default:
python -c "from agent.executor_router import current_mode; print(current_mode())"   # → 'react'

# Confirm fallback works:
RASPUTIN_OMNITOOL_EXECUTOR_MODE=static python -c "
from agent.executor_router import current_mode
print(current_mode())
"   # → 'static'
```

## Phase evidence

Must include (in addition to the standard template):

- Side-by-side trace for the canary goal: static executor vs react executor. Both should produce equivalent artifacts; ReAct should show adaptation visible in the trace.
- Test results matrix: unit tests + real-executor smoke.
- Cost report: total $ spent on real-executor tests during this phase.
- A trace where ReAct recovered from a deliberate tool failure (test #3 above) — paste it.

## Halt conditions specific to Phase 2

- Qwen 27B persistently refuses to emit valid tool_calls JSON. If repeatedly malformed across two prompt iterations, halt and document. The fallback is to feed the model a stricter JSON-mode tool-call grammar. Joshua needs to weigh in.
- Context compaction strategy breaks coherence (the model loses track of prior work). If unit test 12 cannot be made stable, switch to a "summarize old turns" approach (more expensive, more robust). Do not ship coherence loss.
- Real-executor canary cost exceeds $0.50 per run consistently. That means the loop is wasteful; tune `max_steps`, prompt, or observation truncation before approving the phase.

## Out of scope for Phase 2

- Parallel tool calls within a single turn (the OpenAI API supports `parallel_tool_calls`; we'll consider in a future sprint).
- Streaming tokens to the caller (Phase 8).
- Stateful sandbox/browser sessions (Phases 3, 4) — for Phase 2, tools remain stateless per call.
- Sub-agents (Phase 7).
