# become-manus-skill

OpenClaw skill bundle providing agent workflows: research, browse, parse, sandbox-execute, generate multimedia (image / video / audio / music), and deliver multi-format reports.

Built on top of [become-manus-kernel](../become-manus/) for catalog, library-smoke, and deliverable primitives.

## What this skill does

Given a user goal, the skill:

1. **Plans** — 27B emits a typed task list using only tools in the manifest.
2. **Executes** — 27B emits one tool call per turn; a dispatcher runs each tool and feeds results back.
3. **Reviews** — Opus 4.7 inspects the trace and final artifacts; returns APPROVE / REVISE / ABORT.

A REVISE verdict triggers exactly one re-plan cycle. ABORT halts cleanly with a summary.

## Tools (12)

| Tool | Status | Backend |
|---|---|---|
| catalog | available | become_manus_kernel.catalog |
| docling | available | Docling library, sandboxed paths |
| crawl4ai | available | Crawl4AI with URL safety filters |
| sandbox | available | agent-infra/sandbox HTTP API |
| browser | available | Playwright sync (5 actions) |
| deliverables | available | Parameterized kernel.deliverables |
| tts | available | Voxtral TTS, Kokoro fallback |
| stt | available | Whisper-large-v3-turbo |
| image-gen | available | ComfyUI + FLUX.2 [dev] |
| video-gen | deferred | Wan 2.1 (requires 96GB VRAM GPU) |
| music-gen | deferred | MusicGen-Melody (requires audiocraft venv) |
| memory | available | RASPUTIN MCP @ 8808 |

## Models

- **Planner**: Qwen3-27B (OpenCode Zen). Configurable via `BECOME_MANUS_PLANNER_MODEL`.
- **Executor**: same as planner. Configurable via `BECOME_MANUS_EXECUTOR_MODEL`.
- **Reviewer**: Claude Opus 4.7 (Anthropic API). Configurable via `BECOME_MANUS_REVIEWER_MODEL`.

## Install

```bash
# 1. Install the kernel
cd ../become-manus
pip install -e .

# 2. Install the skill
cd ../become-manus-skill
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
