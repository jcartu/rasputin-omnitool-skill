"""tools/stt/index.py — Transcribe audio."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    audio_path = inputs.get("audio_path", "")
    language = inputs.get("language", "auto")

    if not audio_path:
        return {"error": {"code": "FILE_NOT_FOUND", "message": "No audio_path provided"}}
    path = Path(audio_path)
    if not path.exists():
        return {"error": {"code": "FILE_NOT_FOUND", "message": f"File not found: {audio_path}"}}

    from tools.docling._allowed_paths import is_allowed
    if not is_allowed(path):
        return {"error": {"code": "OUTSIDE_ALLOWED_PATH", "message": f"Path outside allowed volumes: {path}"}}

    try:
        from transformers import pipeline
        transcriber = pipeline("automatic-speech-recognition", model="openai/whisper-large-v3-turbo")
        result = transcriber(audio_path)
        transcript = result.get("text", "") if isinstance(result, dict) else ""
        return {
            "result": {
                "transcript": transcript,
                "language_detected": language if language != "auto" else None,
                "model_used": "openai/whisper-large-v3-turbo",
            }
        }
    except Exception as exc:
        logger.warning("whisper_transformers_unavailable", extra={"error": str(exc)})

    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("large-v3-turbo")
        segments, info = model.transcribe(audio_path, language=language if language != "auto" else None)
        transcript = " ".join(seg.text for seg in segments)
        return {
            "result": {
                "transcript": transcript,
                "confidence": info.language_probability,
                "language_detected": info.language,
                "model_used": "whisper-large-v3-turbo",
            }
        }
    except Exception as e:
        return {"error": {"code": "TRANSCRIPTION_FAILED", "message": f"All STT backends failed: {e}"}}


if __name__ == "__main__":
    import json
    import sys
    payload = json.loads(sys.stdin.read())
    print(json.dumps(run(payload)))
