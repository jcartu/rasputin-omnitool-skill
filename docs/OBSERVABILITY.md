# Observability

Real Langfuse-backed tracing and cost telemetry for rasputin-omnitool.

## What Gets Traced

Every significant operation in the agent loop produces a Langfuse span:

- **`run_goal`** — Root trace wrapping the entire goal lifecycle
- **`planner.plan`** — Plan generation (LLM call)
- **`executor.execute`** — Plan execution (tool dispatch loop)
- **`reviewer.review`** — Opus review (LLM call)
- **`tool.<name>`** — Every tool invocation (auto-wrapped by tool registry)

The trace hierarchy looks like:

```
run_goal (generation)
├── planner.plan (span)
├── executor.execute (span)
│   ├── tool.sandbox (span)
│   ├── tool.browser (span)
│   └── tool.tts (span)
└── reviewer.review (span)
```

## Reading a Trace

1. Open Langfuse UI at `http://localhost:3000` (or your configured host)
2. Navigate to **Traces** → find the `run_goal` trace
3. Expand children to see planner, executor, and individual tool spans
4. Each span shows latency, input/output (truncated), and status
5. The root `run_goal` span has `metadata.total_cost_usd` with the cumulative cost

## Setting MAX_COST_USD

Control per-goal spending via environment variable:

```bash
# Default: $0.50 per goal
export RASPUTIN_OMNITOOL_MAX_COST_USD=1.00

# Per-invocation override
RASPUTIN_OMNITOOL_MAX_COST_USD=2.00 python -c "from agent import run_goal; ..."
```

The ceiling is checked **before** each LLM call using estimated token counts. If the next call would push the goal over budget, `CostCeilingExceeded` is raised and the goal halts cleanly.

## Cost Ceiling Behavior

When the ceiling is hit, `run_goal` returns:

```python
{
    "goal_id": "goal-abc123",
    "halted": True,
    "reason": "cost_ceiling_exceeded",
    "details": {"spent": 0.48, "limit": 0.50},
    "results": [],
}
```

The goal does **not** crash. It returns a structured result indicating the halt reason.

## Token-Usage Extraction

Token counts are pulled from LLM responses automatically via `extract_usage()`. Supports:

| SDK | Input field | Output field |
|---|---|---|
| Anthropic | `usage.input_tokens` | `usage.output_tokens` |
| OpenAI / OpenCode Zen | `usage.prompt_tokens` | `usage.completion_tokens` |
| Dict-shaped | `input_tokens` or `prompt_tokens` | `output_tokens` or `completion_tokens` |

If no usage data is available, both counts default to 0.

## Pricing Model

Pricing lives in `agent/observability.py::PRICE_PER_M_TOKENS`. Format: `(input_per_1M, output_per_1M)` in USD.

```python
PRICE_PER_M_TOKENS = {
    "claude-opus-4-7": (15.0, 75.0),
    "claude-sonnet-4-5": (3.0, 15.0),
    "qwen3-27b-instruct": (0.0, 0.0),  # local, free
    "gpt-oss-120b": (0.0, 0.0),        # local, free
}
```

Update this dict when models or pricing change. Unknown models default to $0.

## Disabling Langfuse

Set `LANGFUSE_PUBLIC_KEY=""` (or omit it). The agent loop proceeds normally with no-op observability — no spans, no trace URLs, but cost tracking still works locally.

```bash
# Langfuse disabled, cost tracking still active
unset LANGFUSE_PUBLIC_KEY
unset LANGFUSE_SECRET_KEY
```

## Troubleshooting

### Traces not appearing in Langfuse

1. Verify `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set
2. Verify `LANGFUSE_HOST` points to a running instance (default: `http://localhost:3000`)
3. Check stderr for `Failed to initialize Langfuse client` warnings
4. Run `docker compose --profile cpu ps` to confirm Langfuse containers are healthy

### Costs always zero

1. Check that the model name in `CONFIG` matches a key in `PRICE_PER_M_TOKENS`
2. Verify the LLM response includes a `usage` attribute
3. Add debug logging: `python -c "from agent.observability import extract_usage; print(extract_usage(response))"`

### Langfuse not reachable

The agent loop never crashes due to Langfuse unavailability. If the connection fails, spans are logged as warnings and execution continues.
