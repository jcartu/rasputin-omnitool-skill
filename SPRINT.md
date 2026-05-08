# SPRINT.md — become-manus-skill

## Sprint Goal
Deliver a fully implemented, test-covered Manus-equivalent agent skill with 12 tools, complete agent loop (planner/executor/reviewer), and observability.

## Phases

### PHASE-1: Core Infrastructure ✅
- [x] Project scaffold with Python package structure
- [x] `pyproject.toml` with dependencies and build config
- [x] `manifest.json` — OpenClaw tool contract (12 tools)
- [x] `agent/tool_registry.py` — dynamic tool loading
- [x] `agent/config.py` — configurable cost ceiling, model selection

### PHASE-2: Core Tools ✅
- [x] `catalog` — OSS capability matrix queries
- [x] `docling` — document parsing (DOCX/PDF/HTML → markdown)
- [x] `crawl4ai` — URL crawling with safety guards
- [x] `sandbox` — isolated code execution
- [x] `browser` — Playwright MCP browser automation
- [x] `deliverables` — multi-format output generation (MD/PDF/XLSX/PPTX/CSV)

### PHASE-3: Agent Loop ✅
- [x] `planner.py` — goal-to-plan with tool catalog constraints
- [x] `executor.py` — tool execution with error propagation
- [x] `reviewer.py` — approve/revise/abort quality gate
- [x] `observability.py` — Langfuse tracing integration
- [x] Prompt templates with JSON schema constraints

### PHASE-4: Integration ✅
- [x] Tool registry loads all 12 tools via importlib
- [x] Error handling with typed error codes per tool
- [x] Logging and trace instrumentation
- [x] Configuration-driven model and cost settings

### PHASE-5: Extended Capabilities ✅
- [x] `tts` — text-to-speech (Voxtral/Kokoro fallback)
- [x] `stt` — speech-to-text (Canary-Qwen)
- [x] `image-gen` — image generation via ComfyUI/FLUX.2
- [x] `video-gen` — short video via Wan 2.1
- [x] `music-gen` — music generation via MusicGen-Melody
- [x] `memory` — episodic memory via RASPUTIN MCP

### PHASE-6: Release ✅
- [x] README.md — architecture, tools table, quick start
- [x] SKILL.md — usage guide and model specs
- [x] `examples/cross-tool-smoke.sh` — 12-tool smoke test
- [x] SPRINT.md — this file
- [x] Git tag v0.1.0

## Test Coverage
| Module | Tests | Status |
|---|---|---|
| catalog | 4 | ✅ pass |
| docling | 4 | ✅ pass |
| crawl4ai | 5 | ✅ pass |
| sandbox | 4 | ✅ pass |
| browser | 4 | ✅ pass |
| deliverables | 5 | ✅ pass |
| tts | 3 | ✅ pass |
| stt | 2 | ✅ pass |
| image-gen | 2 | ✅ pass |
| video-gen | 3 | ✅ pass |
| music-gen | 3 | ✅ pass |
| memory | 4 | ✅ pass |
| planner | 4 | ✅ pass |
| reviewer | 4 | ✅ pass |
| **Total** | **63** | **✅ all pass** |

## Delivery Artifacts
- `tools/` — 12 tool implementations
- `agent/` — planner, executor, reviewer, config, observability, tool_registry
- `prompts/` — planner.md, executor.md, reviewer.md
- `tests/` — 63 unit tests
- `examples/` — cross-tool-smoke.sh, start-sandbox.sh
- `manifest.json` — OpenClaw v2026.4 contract
- `SKILL.md` — skill usage documentation
- `README.md` — project overview and quick start
