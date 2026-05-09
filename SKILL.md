# become-manus-skill

OSS-stitched Manus-equivalent agent skill. Research, browse, parse documents, run code in a sandbox, generate images/video/audio, and deliver multi-format reports.

## When to use this skill

Use this skill for goals that require:
- Multi-step research with citation extraction (Crawl4AI + Docling + sandbox).
- Multimedia output: PDFs, slides, illustrative images, narrated audio, short video.
- Web app or static-site generation.
- Long-running goals where memory across sub-tasks matters.

Do NOT use this skill for:
- Pure code authoring (`claw-scaffold` or aider-driven workflows are better).
- Real-time interactive workflows (this skill is async-batch shaped).

## Quick invocation

```python
import os
os.environ["OPENCODE_ZEN_API_KEY"] = "your-key"
os.environ["ANTHROPIC_API_KEY"] = "your-key"

from agent import run_goal
result = run_goal("Research quantum computing and generate a PDF report")
# result["review"].verdict → "APPROVE", "REVISE", or "ABORT"
# result["artifacts"] → list of output file paths
```

## Required environment variables

| Variable | Purpose |
|---|---|
| `OPENCODE_ZEN_API_KEY` | API key for planner/executor model |
| `ANTHROPIC_API_KEY` | API key for reviewer (Claude Opus) |
| `BECOME_MANUS_EXECUTOR_ENDPOINT` | OpenAI-compatible endpoint (default: `http://localhost:11434/v1`) |

## Tools

| Tool | Capability | Status |
|---|---|---|
| catalog | Query the OSS capability matrix | available |
| docling | Parse a document (DOCX/PDF/HTML) into markdown | available |
| crawl4ai | Crawl a URL and return LLM-friendly markdown | available |
| sandbox | Execute code in an isolated agent-infra/sandbox container | available |
| browser | Operate a browser via Playwright MCP | available |
| deliverables | Generate CSV/MD/PDF/XLSX/PPTX outputs | available |
| tts | Synthesize speech from text (Voxtral default) | available |
| stt | Transcribe audio (Whisper default) | available |
| image_gen | Generate images via ComfyUI / FLUX.2 | available |
| video_gen | Generate short video via Wan 2.1 | available |
| music_gen | Generate music via MusicGen-Melody | available |
| memory | Persist and retrieve episodic memory via RASPUTIN MCP | available |

## Models

- Planner: Qwen3-27B (OpenCode Zen, configurable)
- Executor: Qwen3-27B (same)
- Reviewer: Opus 4.7 (Anthropic API, used at checkpoint and end-of-goal)

## Observability

All planner / executor / reviewer / tool calls are traced to `runlog/traces/<goal-id>/` as structured JSON span events.
