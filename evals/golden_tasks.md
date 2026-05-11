# Golden Tasks — v0.4 Eval Suite

10 tasks covering distinct agent-loop behaviors. Each tests a specific category.

## 1. plan-only — Wide research decomposes (plan-only)
**Goal:** Research battery chemistries for EVs in 2026.
**Tests:** Planner decomposes a wide research goal into ≥3 tasks referencing research tools.
**Why it matters:** Verifies the planner can break down complex goals.

## 2. execute-mocked — Agent loop completes (execute-mocked)
**Goal:** Find candidates for 'web_search' capability.
**Tests:** Full agent loop (plan → execute → review) completes without errors when tools are mocked.
**Why it matters:** Validates end-to-end loop integrity without backend dependencies.

## 3. e2e-trivial — Catalog query (execute)
**Goal:** List candidates for 'memory' capability.
**Tests:** Single-step goal completes with APPROVE or REVISE verdict.
**Why it matters:** Baseline e2e sanity check — simplest possible real goal.

## 4. e2e-nontrivial — Multi-step research (execute)
**Goal:** Search for OSS sandboxing tools, summarize top 3, produce markdown report.
**Tests:** Multi-step research goal completes without halting.
**Why it matters:** Tests the agent's ability to chain multiple tool calls.

## 5. cost-ceiling — Budget halt (execute)
**Goal:** Deep multi-source research on computing history.
**Tests:** Goal halts cleanly when $0.001 ceiling is hit (before any real work).
**Why it matters:** Verifies PHASE-3 cost ceiling enforcement works in eval context.

## 6. edge-case — Empty goal (execute)
**Goal:** (empty string)
**Tests:** No Python traceback or unhandled exception.
**Why it matters:** Agent must degrade gracefully on degenerate input.

## 7. execute-mocked — Simple goal (execute-mocked)
**Goal:** Generate a short summary of 'idempotency'.
**Tests:** Simple goal completes in mocked mode.
**Why it matters:** Verifies mocked mode works for straightforward goals.

## 8. plan-only — Tool selection (plan-only)
**Goal:** Build a Python Fibonacci script.
**Tests:** Planner selects ≥1 task referencing ≥1 tool.
**Why it matters:** Validates tool selection logic for coding tasks.

## 9. execute-mocked — Vague goal recovery (execute-mocked)
**Goal:** "Just say 'hello' as a single string output."
**Tests:** No traceback — agent handles vague goal gracefully.
**Why it matters:** Tests robustness against poorly-specified goals.

## 10. e2e-trivial — Sandbox code execution (execute)
**Goal:** Run Python to compute 2^10.
**Tests:** Sandbox-based goal completes without halting.
**Why it matters:** Validates sandbox integration in real execution.
