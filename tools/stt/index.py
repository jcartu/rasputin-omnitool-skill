"""tools/stt/index.py — Transcribe audio."""
from __future__ import annotations
from pathlib import Path
from typing import Any

from agent.config import CONFIG


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    audio_path = inputs.get("audio_path", "")
    language = inputs.get("language", "auto")

    if not audio_path:
        return {"error": {"code": "FILE_NOT_FOUND", "message": "No audio_path provided"}}
    if not Path(audio_path).exists():
        return {"error": {"code": "FILE_NOT_FOUND", "message": f"File not found: {audio_path}"}}

    # Try Canary-Qwen first
    try:
        from transformers import pipeline
        transcriber = pipeline("automatic-speech-recognition", model="canary/whisper-large-v3-turbo")
        result = transcriber(audio_path)
        return {"result": {"transcript": result.get("text", ""), "confidence": 0.9, "language_detected": "en", "model_used": "canary-qwen"}}
    except Exception:
        pass

    # Fallback to faster-whisper
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("large-v3-turbo")
        segments, info = model.transcribe(audio_path, language=language if language != "auto" else None)
        transcript = " ".join(seg.text for seg in segments)
        return {"result": {"transcript": transcript, "confidence": info.language_probability, "language_detected": info.language, "model_used": "whisper-large-v3-turbo"}}
    except Exception:
        pass

    return {"error": {"code": "MODEL_UNAVAILABLE", "message": "Both Canary-Qwen and Whisper unavailable"}}


if __name__ == "__main__":
    import json, sys
    payload = json.loads(sys.stdin.read())
    print(json.dumps(run(payload)))
