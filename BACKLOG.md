# BACKLOG.md

Items deferred from PHASE-2 audit (round 2, APPROVE WITH WAIVER). Must be resolved before PHASE-6 release.

## F-A1 [MINOR] Silent failure swallowing in TTS/STT fallback chains
- **Location:** `tools/tts/index.py:33-34, 48-49`; `tools/stt/index.py:34-35`
- **Issue:** `except Exception: pass` discards diagnostic info about primary backend failure
- **Fix:** Replace with `logger.warning("voxtral failed: %s", exc)` or equivalent observability emit
- **Effort:** Quick (<30 min)

## F-A2 [MINOR] Hardcoded `/home/josh/` path in test_catalog.py
- **Location:** `tests/test_catalog.py:6`
- **Issue:** `sys.path.insert(0, str(Path("/home/josh/workspace/become-manus")))` is portable-hostile
- **Fix:** Delete line — `pip install -e .` already wires kernel into import path
- **Effort:** Quick (<5 min)

## F-A3 [MINOR] STT model deviation — Whisper instead of Canary-Qwen
- **Location:** `tools/stt/index.py:24`
- **Issue:** Brief specifies Canary-Qwen primary; implementation uses `openai/whisper-large-v3-turbo`
- **Fix:** Either add Canary-Qwen as primary or document swap in PHASE-5 evidence
- **Effort:** Short (1-4h if implementing; <30 min if documenting)

## F-A4 [MINOR] Output filenames not unique per-call
- **Location:** `tools/image_gen/index.py:117`, `tools/music_gen/index.py:18`, `tools/video_gen/index.py:115`, `tools/tts/index.py:24`
- **Issue:** Fixed filenames (`image.png`, `music.wav`, etc.) — concurrent goals overwrite each other
- **Fix:** Suffix with `uuid4().hex` or namespace by `goal_id`
- **Effort:** Quick (<30 min)

## F-OpenClaw [DEFERRED] Revisit OpenClaw skills registration
- **Location:** 2-10 / 3-7 / 5-7 rubric checks
- **Issue:** Local workspace skills blocked by OpenClaw symlink-escape prevention
- **Fix:** Revisit once workaround exists (config-time skills-root or publish-to-`~/.openclaw/skills/` step)
- **Effort:** Unknown — depends on OpenClaw configuration options
