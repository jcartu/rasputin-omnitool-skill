# become-manus-skill

Open-source, multi-modal agent skill for async, goal-oriented workflows — research, browsing, document parsing, sandboxed code execution, and multimedia generation (image/video/audio).

## Why this exists

Manus.im is a commercial, closed-source agent platform that orchestrates research, browsing, document parsing, code execution, and multimedia generation into cohesive, multi-step workflows. This project recreates that capability using **open-source components stitched together** — no proprietary APIs, no vendor lock-in.

Built as an [OpenClaw](https://github.com/openclaw) skill bundle, it plugs into the OpenClaw agent framework and provides a drop-in, self-hosted alternative to Manus's agent loop.

### Positioning

| | Manus.im | become-manus-skill | LangGraph | AutoGen | CrewAI |
|---|---|---|---|---|---|
| **License** | Closed-source | MIT | MIT | MIT | MIT |
| **Self-hosted** | No | Yes | Yes | Yes | Yes |
| **Multi-modal** | Yes | Yes (image/video/audio) | No | Limited | No |
| **Agent loop** | Proprietary | Planner→Executor→Reviewer | Custom DSL | Custom DSL | Role-based |
| **Target** | End users | Engineers, researchers | Framework users | Framework users | Framework users |

### Who this is for

- **Engineers** building self-hosted agent workflows without proprietary dependencies
- **Researchers** experimenting with multi-step, multi-modal agent architectures
- **OpenClaw skill authors** looking for a reference implementation of a complex, production-grade skill
- **Teams** replacing Manus.im with an auditable, self-hosted alternative

## Quick start

```bash
pip install -e .
python -c "from agent.tool_registry import load_tools; tools = load_tools(); print(f'{len(tools)} tools loaded')"
```

### Running a goal

```python
import os
os.environ["OPENCODE_ZEN_API_KEY"] = "your-key"
os.environ["ANTHROPIC_API_KEY"] = "your-key"

from agent import run_goal
result = run_goal("Research the latest developments in quantum computing and generate a PDF report")
print(result["review"].verdict)  # "APPROVE", "REVISE", or "ABORT"
```

### Required environment variables

| Variable | Purpose | Default |
|---|---|---|
| `OPENCODE_ZEN_API_KEY` | API key for planner/executor model | (required) |
| `ANTHROPIC_API_KEY` | API key for reviewer (Claude Opus) | (required) |
| `BECOME_MANUS_PLANNER_MODEL` | Model for plan generation | `Qwen3-27B` |
| `BECOME_MANUS_EXECUTOR_MODEL` | Model for tool execution | `Qwen3-27B` |
| `BECOME_MANUS_EXECUTOR_ENDPOINT` | OpenAI-compatible endpoint | `http://localhost:11434/v1` |
| `BECOME_MANUS_REVIEWER_MODEL` | Model for review | `claude-opus-4-7` |
| `BECOME_MANUS_MAX_STEPS` | Max tool calls per goal | `30` |
| `BECOME_MANUS_MAX_WALLCLOCK_MIN` | Max wall-clock time per goal | `20` |

## Architecture

```
┌─────────────────────────────────────────────┐
│  run_goal() — orchestrates the agent loop   │
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

The loop: `run_goal(goal)` → **plan** (LLM generates structured task list) → **execute** (dispatches tools one-at-a-time with placeholder substitution) → **review** (Claude Opus evaluates trace, returns APPROVE/REVISE/ABORT). On REVISE, the loop re-plans once with reviewer feedback.

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
| `stt` | Speech-to-text (Whisper) | ✅ available |
| `image-gen` | Image generation (ComfyUI/FLUX.2) | ✅ available |
| `video-gen` | Short video (Wan 2.1) | ✅ available |
| `music-gen` | Music generation (MusicGen-Melody) | ✅ available |
| `memory` | Episodic memory (RASPUTIN MCP) | ✅ available |

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

All planner/executor/reviewer/tool calls traced to `runlog/traces/<goal-id>/` as structured JSON span events. Langfuse integration is planned for a future phase.

## License

MIT
