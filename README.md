# become-manus-skill

OpenClaw skill bundle scaffold for Manus-equivalent async agent workflows.

This PHASE-2 scaffold declares twelve tool slots, agent loop skeletons, prompts, and placeholder tests. Tool bodies and agent logic are intentionally not implemented yet.

## Status

- Tool entry points return `NOT_IMPLEMENTED`.
- Agent planner, executor, and reviewer functions raise `NotImplementedError`.
- Placeholder tests are skipped until later sprint phases.

## Layout

- `SKILL.md` — skill usage guide.
- `manifest.json` — OpenClaw tool contract manifest.
- `tools/` — twelve scaffolded tool entry points.
- `agent/` — planner/executor/reviewer/config/observability skeletons.
- `prompts/` — system prompts with JSON schema constraints.
- `tests/` — skipped placeholder coverage for future phases.
