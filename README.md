# rasputin-omnitool-skill

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Tests](https://github.com/jcartu/rasputin-omnitool-skill/actions/workflows/tests.yml/badge.svg)](https://github.com/jcartu/rasputin-omnitool-skill/actions/workflows/tests.yml)

OpenClaw skill bundle providing agent workflows: research, browse, parse, sandbox-execute, generate multimedia (image / video / audio / music), and deliver multi-format reports.

Built on top of [rasputin-omnitool](https://github.com/jcartu/rasputin-omnitool) for catalog, library-smoke, and deliverable primitives.

> Formerly `become-manus-skill`. Renamed to `rasputin-omnitool-skill` at v0.2.0. Sprint history (audits, evidence, governance docs) under `runlog/sprint-2026-05/` is preserved as-is.

## What this skill does

Given a user goal, the skill:

1. **Plans** — 27B emits a typed task list using only tools in the manifest.
2. **Executes** — 27B emits one tool call per turn; a dispatcher runs each tool and feeds results back.
3. **Reviews** — Opus 4.7 inspects the trace and final artifacts; returns APPROVE / REVISE / ABORT.

A REVISE verdict triggers exactly one re-plan cycle. ABORT halts cleanly with a summary.

## Tools (12)

| Tool | Status | Backend |
|---|---|---|
| catalog | available | rasputin_omnitool.catalog |
| docling | available | Docling library, sandboxed paths |
| crawl4ai | available | Crawl4AI with URL safety filters |
| sandbox | available | agent-infra/sandbox HTTP API |
| browser | available | Playwright sync (5 actions) |
| deliverables | available | Parameterized rasputin_omnitool.deliverables |
| tts | available | Voxtral TTS, Kokoro fallback |
| stt | available | Whisper-large-v3-turbo |
| image-gen | available | ComfyUI + FLUX.2 [dev] |
| video-gen | deferred | Wan 2.1 (requires 96GB VRAM GPU) |
| music-gen | deferred | MusicGen-Melody (requires audiocraft venv) |
| memory | available | RASPUTIN MCP @ 8808 |

## Models

- **Planner**: Qwen3-27B (OpenCode Zen). Configurable via `RASPUTIN_OMNITOOL_PLANNER_MODEL`.
- **Executor**: same as planner. Configurable via `RASPUTIN_OMNITOOL_EXECUTOR_MODEL`.
- **Reviewer**: Claude Opus 4.7 (Anthropic API). Configurable via `RASPUTIN_OMNITOOL_REVIEWER_MODEL`.

## Install

```bash
# 1. Install the kernel
cd ../rasputin-omnitool
pip install -e .

# 2. Install the skill
cd ../rasputin-omnitool-skill
pip install -e .
```

## Run a goal

```bash
./examples/run-demo.sh
# Or programmatically:
python -c "
from agent import run_goal
result = run_goal('Crawl http://example.com and produce a 1-paragraph markdown summary saved to outputs/.')
print(result['review'].verdict)
"
```

## Tests

```bash
pytest  # 75 tests
```

## Observability

All planner / executor / reviewer / tool calls are traced to `runlog/traces/<goal-id>/` as structured JSON span events. Langfuse integration is deferred to post-sprint.

## Skill manifest

OpenClaw consumes `manifest.json` to know what tools the skill provides. See it for full input/output/error schemas per tool.

## License

MIT.
