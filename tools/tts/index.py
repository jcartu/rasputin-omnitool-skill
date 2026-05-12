"""tools/tts/index.py — Synthesize speech from text."""
from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any

from agent.config import CONFIG
from agent.artifact_registry import get_registry

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
            result = {"audio_path": str(path), "duration_s": 0, "model_used": "voxtral"}
            return {"result": _with_artifact(result, path, goal_id)}
    except Exception as exc:
        logger.warning("voxtral_unavailable", extra={"error": str(exc)})

    # Fallback to Kokoro
    try:
        from kokoro_onnx import Kokoro
        kokoro = Kokoro()
        samples, sample_rate = kokoro.create(text, voice=voice)
        import wave
        import struct
        with wave.open(str(path), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(struct.pack("<" + "h" * len(samples), *samples))
        result = {"audio_path": str(path), "duration_s": len(samples) / sample_rate, "model_used": "kokoro"}
        return {"result": _with_artifact(result, path, goal_id)}
    except Exception as exc:
        logger.warning("kokoro_unavailable", extra={"error": str(exc)})

    return {"error": {"code": "MODEL_UNAVAILABLE", "message": "Both Voxtral and Kokoro unavailable"}}


def _with_artifact(result: dict[str, Any], path: Path, goal_id: str | None) -> dict[str, Any]:
    art = get_registry().add(path, produced_by="tts/run", goal_id=goal_id or "ad-hoc")
    result["artifact_id"] = art.id
    result["artifact"] = {
        "id": art.id,
        "path": art.path,
        "kind": art.kind,
        "media_type": art.media_type,
        "size_bytes": art.size_bytes,
        "content_hash": art.content_hash,
    }
    return result


if __name__ == "__main__":
    import json
    import sys
    payload = json.loads(sys.stdin.read())
    print(json.dumps(run(payload)))
