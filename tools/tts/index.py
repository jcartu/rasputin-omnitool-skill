"""tools/tts/index.py — Synthesize speech from text."""
from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from pathlib import Path
from typing import Any

from agent.config import CONFIG

logger = logging.getLogger(__name__)


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    text = inputs.get("text", "")
    voice = inputs.get("voice", "voxtral-female-1")
    fmt = inputs.get("format", "wav")

    if not text:
        return {"error": {"code": "SYNTHESIS_FAILED", "message": "Empty text"}}
    if fmt not in ("wav", "mp3"):
        return {"error": {"code": "SYNTHESIS_FAILED", "message": f"Unsupported format: {fmt}"}}

    voxtral_url = os.environ.get("RASPUTIN_OMNITOOL_VOXTRAL_URL", "http://127.0.0.1:8810")
    output_dir = Path(CONFIG.outputs_dir) / "audio"
    output_dir.mkdir(parents=True, exist_ok=True)
    goal_id = inputs.get("_goal_id", f"adhoc-{uuid.uuid4().hex}")
    step_id = inputs.get("_step_id", "step")
    path = output_dir / f"{goal_id}-{step_id}.{fmt}"

    # Try Voxtral first
    try:
        import httpx
        resp = httpx.post(f"{voxtral_url}/v1/tts", json={"text": text, "voice": voice, "format": fmt}, timeout=60)
        if resp.status_code == 200:
            path.write_bytes(resp.content)
            return {"result": {"audio_path": str(path), "duration_s": 0, "model_used": "voxtral"}}
    except Exception as exc:
        logger.warning("voxtral_unavailable", extra={"error": str(exc)})

    # Fallback to Kokoro
    try:
        from kokoro_onnx import Kokoro
        kokoro = Kokoro()
        samples, sample_rate = kokoro.create(text, voice=voice)
        import wave, struct
        with wave.open(str(path), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(struct.pack("<" + "h" * len(samples), *samples))
        return {"result": {"audio_path": str(path), "duration_s": len(samples) / sample_rate, "model_used": "kokoro"}}
    except Exception as exc:
        logger.warning("kokoro_unavailable", extra={"error": str(exc)})

    return {"error": {"code": "MODEL_UNAVAILABLE", "message": "Both Voxtral and Kokoro unavailable"}}


if __name__ == "__main__":
    import json, sys
    payload = json.loads(sys.stdin.read())
    print(json.dumps(run(payload)))
