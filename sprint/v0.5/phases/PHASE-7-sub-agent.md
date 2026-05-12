# PHASE 7 — Sub-agent tool (parallel)

**Branch:** `sprint/v0.5-phase7`
**Estimated effort:** 4–5 hours
**Depends on:** Phase 6 approved

## Objective

Add a first-class `sub_agent` tool that lets the executor spawn N parallel sub-agents to run independent sub-goals, then return aggregated results to the parent. Replaces the deleted `wide_research` tool with a generic capability that handles all wide-fanout patterns.

## Why

The single most useful pattern from Manus is "research 20 papers in parallel and summarize." Manus achieves this by spinning up sub-processes per fan-out item. The current rasputin loop is single-threaded by construction. Without sub-agents, "wide" work is sequential and slow, and a single failure halts the whole goal.

## Architecture

### The tool

`tools/sub_agent/index.py` exposes operation `run_parallel`:

```python
def run(inputs: dict) -> dict:
    """
    Inputs:
      sub_goals: list of strings, each a self-contained sub-goal
      max_concurrent: int, default 4
      max_depth: int, current depth + 1 must not exceed this; default ceiling 2
      budget_usd_per_sub: float, default 0.10
      timeout_min_per_sub: int, default 5
      tool_allowlist: list of tool names sub-agents may use, optional
      tool_denylist: list of tool names sub-agents may NOT use, default ['sub_agent']
    Outputs:
      results: list of {sub_goal, status, summary, artifact_ids, cost_usd, halted_for?}
      aggregate_cost_usd: float
      successful_count: int
      failed_count: int
    """
```

Each sub-goal runs as a full ReAct loop (`run_goal()` recursively) with:
- Isolated message history (sub-agents do not see parent context).
- Inherited artifact registry (results go into the same DB, tagged with `sub_agent_id`).
- A new `goal_id` derived from parent (e.g. `<parent>/sub-1`).
- Optional tool restrictions per call.

### Recursion limit

`sub_agent` is in the denylist by default — sub-agents cannot themselves spawn sub-agents. Joshua can override but the depth ceiling stops infinite recursion regardless.

### Parallelism

Use `concurrent.futures.ThreadPoolExecutor` with `max_workers=max_concurrent`. Each sub-goal runs in a worker thread; thread isolation is fine because `run_goal()` is process-local and each call has its own context.

Note: thread-based, not multiprocessing. The model calls are I/O-bound (HTTP); the GIL is not a problem.

### Budget

Sub-agents inherit a *fraction* of the parent's remaining budget. Specifically:
- Parent passes `budget_usd_per_sub`.
- If total `sum(budget_usd_per_sub for s in sub_goals) > parent_remaining_budget`, raise `INSUFFICIENT_BUDGET` before spawning any sub.
- After parallel completion, the parent's cost accumulator is incremented by `aggregate_cost_usd`.

### Result aggregation

Each sub-agent returns its `Review` plus a "summary" that the sub-agent's ReAct executor emits as its final answer. The parent receives a list of dicts; it's the parent's job (driven by its own ReAct loop) to synthesize them.

## Skeleton

See `skeletons/sub_agent_tool.py`. Includes:
- The `run()` entrypoint.
- The thread pool driver.
- Result serialization.
- Budget pre-flight check.
- Tool allowlist/denylist enforcement (via a wrapped `load_tools()` per sub).

## Files to change

```
A  tools/sub_agent/__init__.py
A  tools/sub_agent/index.py
A  tools/sub_agent/manifest.json
M  manifest.json                          # register the new tool
M  agent/__init__.py                      # support tool_allowlist/denylist in run_goal
M  agent/react_executor.py                # ditto, propagate restrictions
M  agent/tool_registry.py                 # load_tools(allowlist=, denylist=)
A  tests/test_sub_agent.py
```

## Acceptance criteria

- `pytest -v tests/test_sub_agent.py` passes (12+ tests).
- Parallel fan-out of 4 sub-goals completes in roughly max(per-sub-time) + overhead, not sum().
- Recursion is blocked by default: sub-agent attempts to call `sub_agent` → `TOOL_NOT_ALLOWED`.
- Tool allowlist/denylist works: a sub spawned with `tool_allowlist=['crawl4ai']` cannot call `sandbox`.
- Budget overrun pre-flight check fires before any sub is spawned.
- Sub-agents register their artifacts with the parent's goal_id but tagged with `sub_agent_id`.
- One sub failing does not halt the others; failures are surfaced in the aggregate result.
- Aggregate cost is correctly accumulated to the parent.

## Unit-test scenarios that MUST exist

1. Empty `sub_goals` → `INVALID_INPUT`.
2. Single sub: same shape as parent `run_goal` result.
3. 4 parallel subs all succeed → 4 results, aggregate cost = sum.
4. 1 of 4 subs fails (returns ABORT) → 3 results succeed + 1 failure record; parent not halted.
5. Budget pre-flight blocks oversized fan-out before spawning.
6. Recursion blocked by default denylist.
7. Recursion permitted when explicit override → still capped by `max_depth`.
8. Allowlist enforced: forbidden tool used in sub → `TOOL_NOT_ALLOWED`.
9. Timeout per sub: a sub that runs over time is killed; record shows `halted_for: 'WALLCLOCK'`.
10. Artifacts produced in subs are queryable from parent via the registry, tagged with `sub_agent_id`.
11. Two parallel subs writing the same content hash: dedup works across subs.
12. The trace of the parent shows a single `sub_agent/...` step with structured aggregate output.

## Self-verification

```bash
pytest -v tests/test_sub_agent.py 2>&1 | tee sprint/v0.5/phase-7-pytest.log

# Live demo: 3 parallel research sub-goals
python -c "
from agent import run_goal
r = run_goal('''
Run three parallel research sub-goals via the sub_agent tool:
1. \"Brief overview of CRDT consistency models\"
2. \"Recent (2024-2026) progress in zk-SNARK proof systems\"
3. \"State of the art in retrieval-augmented generation\"
Synthesize the three results into one 500-word executive summary saved as outputs/exec_summary.md.
''')
print('verdict:', r['review'].verdict)
print('cost:', r.get('cost_usd'))
print('artifacts:', r['artifacts'])
" 2>&1 | tee sprint/v0.5/phase-7-live-demo.log
```

## Phase evidence

- Test results.
- Live demo output: 3-parallel-research → exec_summary.md.
- A wall-clock comparison: same 3 sub-goals run serially vs parallel; parallel must be ≥2x faster.
- A trace showing the parent's view of the sub_agent step (compact aggregate, not the full sub trace).

## Halt conditions specific to Phase 7

- If parallel sub-agents experience contention on the artifact DB (SQLite write lock), halt and propose either (a) WAL mode or (b) a per-process write queue. Do not ignore database locking errors.
- If the local Qwen 27B can't sustain N parallel inference calls because the endpoint is single-tenant, document and recommend either (a) batching or (b) routing parallel sub-agents to different model endpoints. Sisyphus should *not* serialize the parallel calls silently to hide the limitation.

## Out of scope for Phase 7

- Streaming results from a sub to the parent (Phase 8).
- Sub-agents on remote machines.
- Sub-agent specialization (different models per sub).
- Sub-agent quotas beyond budget and timeout.
- Communication between subs.
