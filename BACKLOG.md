# BACKLOG.md

Items deferred from PHASE-2 audit (round 2, APPROVE WITH WAIVER). Must be resolved before PHASE-6 release.

## F-A1 [RESOLVED] Silent failure swallowing in TTS/STT fallback chains
- **Location:** `tools/tts/index.py`; `tools/stt/index.py`
- **Issue:** `except Exception: pass` discards diagnostic info about primary backend failure
- **Fix:** Replaced with `logger.warning(...)` with structured extra context
- **Resolved:** v0.4 sprint PHASE-0 truth pass

## F-A2 [RESOLVED] Hardcoded `/home/josh/` path in test_catalog.py
- **Location:** `tests/test_catalog.py:6`
- **Issue:** `sys.path.insert(0, str(Path("/home/josh/workspace/become-manus")))` is portable-hostile
- **Fix:** Deleted line — `pip install -e .` already wires kernel into import path
- **Resolved:** Commit `3a43866` (PHASE-3)
## F-A3 [RESOLVED] STT model deviation — Whisper instead of Canary-Qwen
- **Location:** `tools/stt/index.py:24`, `SKILL.md`
- **Issue:** Brief specifies Canary-Qwen primary; implementation uses `openai/whisper-large-v3-turbo`
- **Fix:** Documented Whisper as actual default in SKILL.md (Option B per PHASE-0 brief)
- **Resolved:** v0.4 sprint PHASE-0 truth pass

## F-A4 [RESOLVED] Output filenames not unique per-call
- **Location:** `tools/image_gen/`, `tools/music_gen/`, `tools/video_gen/`, `tools/tts/`, `tools/deliverables/`
- **Issue:** Fixed filenames (`image.png`, `music.wav`, etc.) — concurrent goals overwrite each other
- **Fix:** All output filenames now include `goal_id` + `step_id` prefix (falls back to timestamp)
- **Resolved:** v0.4 sprint PHASE-0 truth pass

## F-OpenClaw [DEFERRED] Revisit OpenClaw skills registration
- **Location:** 2-10 / 3-7 / 5-7 rubric checks
- **Issue:** Local workspace skills blocked by OpenClaw symlink-escape prevention
- **Fix:** Revisit once workaround exists (config-time skills-root or publish-to-`~/.openclaw/skills/` step)
- **Effort:** Unknown — depends on OpenClaw configuration options
- **Waived:** PHASE-2, PHASE-3, PHASE-5 per PHASE-2-WAIVER.md extension

## F-PHASE5-Langfuse [DEFERRED] Langfuse observability infrastructure
- **Location:** rubric 5-8, 5-9
- **Issue:** Self-hosted Langfuse deployment + SDK swap not completed
- **Fix:** Deploy Langfuse via docker-compose, swap `agent/observability.py` to use Langfuse SDK
- **Deferred to:** PHASE-6 per PHASE-2-WAIVER.md extension

## F-PHASE5-Promptfoo [DEFERRED] Promptfoo eval harness
- **Location:** rubric 5-10, 5-11
- **Issue:** `evals/promptfoo.yaml` not created, 5 golden evals not run
- **Fix:** Install promptfoo, author evals, run them
- **Deferred to:** PHASE-6 per PHASE-2-WAIVER.md extension

## F-PHASE5-Multimodal [DEFERRED] Multimodal end-to-end demo
- **Location:** rubric 5-12, 5-13
- **Issue:** `examples/run-multimodal-demo.sh` not created, no cost tracking
- **Fix:** Create demo script, run it, capture transcript
- **Deferred to:** PHASE-6 per PHASE-2-WAIVER.md extension
