# Changelog

## v0.5.0-rc1 (2026-05-12)

### New Features

- **ReAct Executor** (Phase 2): Model-in-the-loop agent with OpenAI tool calls, cost ceiling, wall-clock timeout, step limit, structured trace output. ReAct is now the default executor mode.
- **Tool Metadata** (Phase 1): `load_tool_metadata()` with TTL cache, probes each tool manifest + index.py, returns availability status including broken tools.
- **Sandbox Sessions** (Phase 3): Docker-based sandbox with session persistence, state survives container restart.
- **Browser Sessions** (Phase 4): Stateful browser via Playwright with session persistence, session manager.
- **Checkpoint/Resume** (Phase 5): Survives kill -9, resume from last checkpoint.
- **Artifact Registry** (Phase 6): Content-hash dedup, typed files, lineage tracking, tagging.
- **Sub-Agent Tool** (Phase 7): Parallel fan-out via ThreadPoolExecutor, recursion blocking, budget pre-flight, allowlist/denylist.

### Breaking Changes

None. All changes are backwards compatible.

### API Changes

- `run_goal()` signature expanded: added `tool_allowlist`, `tool_denylist`, `_budget_usd`, `_max_wallclock_min`, `_depth`, `_parent_goal_id`. All new params default to None/empty.
- `load_tools()` signature expanded: added `allowlist`, `denylist` kwargs.

### Tool Changes

- Tool count: 16 → 17
- Added: `sub_agent` (parallel sub-agent spawning)
- Removed: `webapp_builder`, `wide_research`
- `manifest.json` regenerated to reflect current tool set

### Configuration

- New env var: `RASPUTIN_OMNITOOL_EXECUTOR_MODE` (default: `react`, override with `static`)
- New env var: `RASPUTIN_OMNITOOL_EXECUTOR_ENDPOINT` (default: `http://localhost:11434/v1`)
- New config: `browser_session_root` for browser session persistence

### Test Coverage

- Tests: 121 → 229 (+108)
- Skipped: 6 (crawl4ai/SearXNG real-backend tests)

### Known Issues

- crawl4ai: broken due to lxml 6.0.2 incompatibility (requires 5.3)
- web_search: SearXNG at localhost:8889 returns 404
- Golden goals: not executed end-to-end (blocked by above issues)
- Streaming (Phase 8): deliberately deferred

### Migration Guide

- **No action required** for existing users. All changes are backwards compatible.
- To use the static executor (legacy mode), set `RASPUTIN_OMNITOOL_EXECUTOR_MODE=static`.
- The ReAct executor is the default. If you were relying on static execution, set the env var above.
