# Evals

Promptfoo-based eval harness for rasputin-omnitool-skill. 10 golden tasks covering plan-only, execute, execute-mocked, cost-ceiling, and edge-case categories.

## What Evals Exist

10 tasks in `evals/promptfoo.yaml`, documented in `evals/golden_tasks.md`:

| # | Category | Mode | Description |
|---|----------|------|-------------|
| 1 | plan-only | plan-only | Wide research decomposes into ≥3 tasks |
| 2 | execute-mocked | execute-mocked | Agent loop completes without errors |
| 3 | e2e-trivial | execute | Catalog query completes with verdict |
| 4 | e2e-nontrivial | execute | Multi-step research with deliverable |
| 5 | cost-ceiling | execute | Budget halt at $0.001 ceiling |
| 6 | edge-case | execute | Empty goal returns clean error |
| 7 | execute-mocked | execute-mocked | Simple goal in mocked mode |
| 8 | plan-only | plan-only | Tool selection for coding task |
| 9 | execute-mocked | execute-mocked | Vague goal recovery |
| 10 | e2e-trivial | execute | Sandbox code execution |

## How to Run Evals Locally

```bash
# Install promptfoo (if not already)
npm install -g promptfoo

# Run all evals
promptfoo eval --config evals/promptfoo.yaml --output report.html

# Open the report
open report.html  # or equivalent
```

Expected: ~5-10 minutes wall-clock, ~$2-5 in API costs (plan-only and execute-mocked tasks are free).

## How to Read the Report

The HTML report shows:
- **Pass/Fail** per test
- **Latency** per test
- **Output** (JSON-serialized agent result)
- **Assertion details** (which assertions passed/failed)

## How to Add a New Eval

1. Add a new `tests:` entry to `evals/promptfoo.yaml`
2. Set `vars.goal` to the goal string
3. Set `options.provider.config.mode` to `plan-only`, `execute`, or `execute-mocked`
4. Add `assert:` blocks (JavaScript assertions returning boolean)
5. Document in `evals/golden_tasks.md`

Example:
```yaml
- description: my-new-eval — brief description
  vars:
    goal: "My goal string"
  options:
    provider:
      config:
        mode: execute-mocked
        max_cost_usd: 0.10
  assert:
    - type: javascript
      value: |
        const out = JSON.parse(output);
        return out.halted === false;
```

## The `[run-evals]` PR Label

Evals only run in CI when a PR has the `run-evals` label. This prevents burning API budget on every PR. To run evals:

1. Add the `run-evals` label to the PR
2. CI runs the full eval suite
3. Report is uploaded as an artifact

## Cost Ceiling for Evals

Each test can set `max_cost_usd` in the provider config. The cost ceiling (PHASE-3) enforces it. Default: $0.50. Override per test as needed.

## Mocking Tool Backends

Set `mode: execute-mocked` to use canned tool outputs. The agent loop runs end-to-end but tools return `{"result": {"_mock": true, "_tool": "name", "_inputs": {...}}}`. Useful for testing loop logic without backend dependencies.

## Pitfalls

- **Network flakes:** e2e tests depend on real backends. Failures may be transient.
- **Model variance:** Planner output can vary between runs. Assertions should be tolerant.
- **Time-sensitive queries:** Goals referencing current events may produce stale results.
