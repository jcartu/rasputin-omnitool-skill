# Contributing to rasputin-omnitool-skill

This is a working agent skill — a planner / executor / reviewer loop with 12 tools. Contributions are welcome but please read this first.

## What belongs here

- New tools that fit the manifest contract (`manifest.json`).
- Improvements to planner / executor / reviewer prompts (with eval evidence).
- Tool reliability fixes (timeouts, retries, error normalization).
- Test coverage for tool dispatchers.
- Sandbox path-safety and URL-safety filters.

## What doesn't belong here

- Catalog or license-review changes — those go in [rasputin-omnitool](https://github.com/jcartu/rasputin-omnitool) (the kernel).
- New LLM clients without a justification (current set: Anthropic SDK + OpenAI-compatible endpoint for OpenCode Zen).
- Tools that bypass the manifest. Every tool must declare its inputs/outputs/errors.

## Workflow

1. Open an issue first for non-trivial changes.
2. Branch from `master`: `feat/<short-name>` or `fix/<short-name>`.
3. Tests must pass: `pytest`. The suite has 75 tests covering all 12 tools.
4. If you change planner/executor/reviewer behavior, run a goal end-to-end before opening a PR.
5. Commit messages: imperative mood, summary in 72 chars or less.

## Adding a tool

1. Add the tool entry to `manifest.json` with full input/output/error schema.
2. Implement `tools/<name>/index.py` exposing `run(input: dict) -> dict`.
3. Add unit tests in `tests/test_<name>.py` covering happy path + each declared error code.
4. Document the backend dependency in `SKILL.md`.
5. If the tool requires environment variables, prefix them with `RASPUTIN_OMNITOOL_`.

## Tests

```bash
pip install -e .[dev]
pytest
```

The suite is mostly offline. A few tests skip if external services aren't available (sandbox container, ComfyUI, RASPUTIN MCP) — those are fine to skip locally.

## Sprint governance

This project ran a phased sprint with audited deliverables. The audit trail under `runlog/sprint-2026-05/` is preserved as a historical record. New work doesn't need to follow the sprint format, but if you're proposing a multi-phase change, mirror the structure (PHASE-N-evidence.md / PHASE-N-audit.md).

## Code of Conduct

Be civil. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
