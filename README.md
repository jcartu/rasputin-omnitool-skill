<p align="center">
<img src=".github/assets/logo-mark.png" alt="rasputin-omnitool-skill" width="80"/>
</p>

<p align="center">
<img src=".github/assets/hero.png" alt="rasputin-omnitool-skill hero" width="100%"/>
</p>

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Tests](https://github.com/jcartu/rasputin-omnitool-skill/actions/workflows/tests.yml/badge.svg)](https://github.com/jcartu/rasputin-omnitool-skill/actions/workflows/tests.yml)
OpenClaw skill bundle providing agent workflows: research, browse, parse, sandbox-execute, generate multimedia (image / video / audio / music), and deliver multi-format reports.

Built on top of [rasputin-omnitool](https://github.com/jcartu/rasputin-omnitool) for catalog, library-smoke, and deliverable primitives.

> Formerly `become-manus-skill`. Renamed to `rasputin-omnitool-skill` at v0.2.0. Sprint history (audits, evidence, governance docs) under `runlog/sprint-2026-05/` is preserved as-is.

## What this skill does

Given a user goal, the skill:

1. **Plans** — Planner model emits a typed task list using only tools in the manifest.
2. **Executes** — Dispatcher runs each tool and feeds results back.
3. **Reviews** — Opus 4.7 inspects the trace and final artifacts; returns APPROVE / REVISE / ABORT.

A REVISE verdict triggers exactly one re-plan cycle. ABORT halts cleanly with a summary.

## Tools (16)

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
| image_gen | available | ComfyUI + FLUX.2 [dev] |
| video_gen | deferred | Wan 2.1 (requires 96GB VRAM GPU) |
| music_gen | deferred | MusicGen-Melody (requires audiocraft venv) |
| memory | available | RASPUTIN MCP @ 8808 |
| web_search | available | SearXNG |
| slides | available | Marp CLI (PDF/HTML/PPTX) |
| mail | available | Himalaya CLI (IMAP/SMTP) |
| coding_agent | available | aider subprocess |

## Models

- **Planner**: Configurable via `RASPUTIN_OMNITOOL_PLANNER_MODEL` (default: `gpt-oss-120b`).
- **Executor**: Same as planner. Configurable via `RASPUTIN_OMNITOOL_EXECUTOR_MODEL`.
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
pytest  # 121 tests
```

## Observability

Real Langfuse-backed tracing. All planner / executor / reviewer / tool calls produce spans with token counts and dollar costs. Cost ceiling enforcement halts goals cleanly when `RASPUTIN_OMNITOOL_MAX_COST_USD` is exceeded.

See [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md).

## Evals

Promptfoo eval harness with 10 golden tasks. CI runs on PRs with `[run-evals]` label.

See [docs/EVALS.md](docs/EVALS.md).

## User Surface

Open WebUI plugin for chat-driven goal invocation. Streams executor status to chat, returns verdict + artifacts.

See [docs/OPEN_WEBUI_SETUP.md](docs/OPEN_WEBUI_SETUP.md).

## Compose Stack

Docker Compose with 3 profiles (cpu, gpu-single, gpu-multi). Bundles sandbox, SearXNG, and ComfyUI.

See [docs/COMPOSE.md](docs/COMPOSE.md).

## Skill manifest

OpenClaw consumes `manifest.json` to know what tools the skill provides. See it for full input/output/error schemas per tool.

## License

MIT.
