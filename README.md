# become-manus-skill

Open-source, multi-modal agent skill for async, goal-oriented workflows — research, browsing, document parsing, sandboxed code execution, and multimedia generation (image/video/audio).

## Quick start

```bash
pip install -e .
python -c "from agent.tool_registry import load_tools; tools = load_tools(); print(f'{len(tools)} tools loaded')"
```

## Architecture

```
┌─────────────────────────────────────────────┐
│  Orchestrator (agent loop)                  │
│  ┌─────────┐  ┌─────────┐  ┌────────────┐  │
│  │ Planner │→│ Executor│→│  Reviewer  │  │
│  └────┬────┘  └────┬────┘  └────┬───────┘  │
│       │            │            │           │
│       └────────────┼────────────┘           │
│                    ↓                        │
│  ┌──────────────────────────────────────┐   │
│  │  Tool Registry (12 tools)            │   │
│  │  catalog | docling | crawl4ai        │   │
│  │  sandbox | browser | deliverables    │   │
│  │  tts | stt | image-gen | video-gen  │   │
│  │  music-gen | memory                 │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

## Tools

| Tool | Capability | Status |
|---|---|---|
| `catalog` | Query OSS capability matrix | ✅ available |
| `docling` | Parse DOCX/PDF/HTML → markdown | ✅ available |
| `crawl4ai` | Crawl URLs → LLM-friendly markdown | ✅ available |
| `sandbox` | Execute code in isolated container | ✅ available |
| `browser` | Browser automation via Playwright MCP | ✅ available |
| `deliverables` | Generate CSV/MD/PDF/XLSX/PPTX | ✅ available |
| `tts` | Text-to-speech (Voxtral/Kokoro) | ✅ available |
| `stt` | Speech-to-text (Canary-Qwen) | ✅ available |
| `image-gen` | Image generation (ComfyUI/FLUX.2) | ✅ available |
| `video-gen` | Short video (Wan 2.1) | ✅ available |
| `music-gen` | Music generation (MusicGen-Melody) | ✅ available |
| `memory` | Episodic memory (RASPUTIN MCP) | ✅ available |

## Models

- **Planner/Executor**: Qwen3.5-27B (OpenCode Zen, configurable)
- **Reviewer**: Opus 4.7 (Anthropic API)
- **Cost ceiling**: <$0.10 per goal (configurable in `agent/config.py`)

## Layout

- `agent/` — planner, executor, reviewer, config, observability
- `tools/` — 12 tool implementations
- `prompts/` — system prompts with JSON schema constraints
- `tests/` — 63 tests covering all tools and agent loop
- `examples/` — smoke tests and sandbox setup
- `manifest.json` — OpenClaw tool contract manifest
- `SKILL.md` — skill usage guide

## Testing

```bash
python -m pytest --tb=short -v  # 63 tests
```

## Observability

All planner/executor/reviewer/tool calls traced via Langfuse. Deploy via `examples/langfuse-up.sh`.

## License

MIT
