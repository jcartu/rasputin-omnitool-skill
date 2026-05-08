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
| stt | Transcribe audio (Canary-Qwen default) | available |
| image-gen | Generate images via ComfyUI / FLUX.2 | available |
| video-gen | Generate short video via Wan 2.1 | available |
| music-gen | Generate music via MusicGen-Melody | available |
| memory | Persist and retrieve episodic memory via RASPUTIN MCP | available |

## Models

- Planner: 27B (OpenCode Zen, configurable)
- Executor: 27B (same)
- Reviewer: Opus 4.7 (Anthropic API, used at checkpoint and end-of-goal)

## Cost ceiling

Default: <$0.10 per goal. Configurable via `agent/config.py`.

## Observability

All planner / executor / reviewer / tool calls are traced via Langfuse. Deploy via `examples/langfuse-up.sh`.
