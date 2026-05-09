# PHASE-3 evidence — Core tools (verification phase)

## Phase brief
phases/PHASE-3-core-tools.md

**Note:** PHASE-3 is a verification phase per PHASE-2 waiver. All 6 core tools were implemented in a prior session and retroactively verified against the 3-* rubric during PHASE-2 re-audit (round 2, APPROVE WITH WAIVER). This phase confirms those results with live tests.

## What was done (per sub-task)
- [✅] 3.1 — tools/catalog verified
  - commit: 3a43866 fix: remove hardcoded /home/josh/ from test_catalog.py (F-A2)
  - tests: 5 passed in 0.03s
  - live: no filter → 54 candidates, capability filter → 4 candidates, invalid → INVALID_CAPABILITY, license → 27 MIT, empty → NO_MATCH
  - notes: F-A2 (hardcoded path) fixed during this phase
- [✅] 3.2 — tools/docling verified
  - tests: 3 passed, 2 skipped (docling not installed in this venv)
  - notes: error paths (FILE_NOT_FOUND, OUTSIDE_ALLOWED_PATH, no path) all tested; live parsing deferred to PHASE-5 when docling is installed
- [✅] 3.3 — tools/crawl4ai verified
  - tests: 6 passed in 0.02s
  - notes: SSRF protection verified (file://, ftp://, loopback, private IP, link-local all blocked; env override works)
- [✅] 3.4 — tools/sandbox verified
  - tests: 8 passed in 0.41s
  - notes: all 4 operations tested, error paths (SANDBOX_UNREACHABLE, TIMEOUT, INVALID_OPERATION) covered
- [✅] 3.5 — tools/browser verified
  - tests: 6 passed in 1.75s
  - notes: Playwright sync API (Option A), all 5 actions tested, error paths covered
- [✅] 3.6 — tools/deliverables verified
  - tests: 6 passed in 0.84s
  - notes: all formats tested (md, pdf, xlsx, pptx, csv, html, png chart), error paths covered

## Help requests this phase
- None.

## ETA performance
- Target: 8h
- Actual: ~30 min (verification only, no implementation needed)
- Slippage reason: N/A — under target by wide margin (waiver reduced scope to verification)

## Final tree (relevant subset)
```
tools/catalog/index.py
tools/docling/index.py, _allowed_paths.py
tools/crawl4ai/index.py
tools/sandbox/index.py
tools/browser/index.py, README.md
tools/deliverables/index.py
tools/tts/index.py
tools/stt/index.py
tools/image_gen/index.py
tools/video_gen/index.py
tools/music_gen/index.py
tools/memory/index.py
agent/planner.py, executor.py, reviewer.py, observability.py, config.py, tool_registry.py, __init__.py
prompts/planner.md, executor.md, reviewer.md
tests/test_catalog.py, test_docling.py, test_crawl4ai.py, test_sandbox.py, test_browser.py, test_deliverables.py, test_extended_tools.py, tools_unit.py, loop_integration.py
```

## Final test summary
```
pytest tests/ -q → 70 passed, 2 skipped in 3.26s
```

## Things I'm unsure about
- Docling live parsing (3-2) is deferred — docling not installed in this venv. The error paths are tested; live parsing will be verified in PHASE-5.
- OpenClaw registration (3-7/3-12) remains N/A — same symlink-escape blocker as PHASE-2.

## Open questions for Opus
- PHASE-3 is a verification phase per waiver. The retroactive 3-* checks from PHASE-2 audit.v2.md are re-stated here. No new implementation was needed.
