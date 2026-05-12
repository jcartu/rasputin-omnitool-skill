"""tools/music_gen/index.py — Generate music via MusicGen-Melody."""
from __future__ import annotations
from pathlib import Path
import uuid
from typing import Any

from agent.config import CONFIG
from agent.artifact_registry import get_registry


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    prompt = inputs.get("prompt", "")
    duration_s = min(inputs.get("duration_s", 15), 60)

    if not prompt:
        return {"error": {"code": "GENERATION_FAILED", "message": "Empty prompt"}}

    output_dir = Path(CONFIG.outputs_dir) / "music"
    output_dir.mkdir(parents=True, exist_ok=True)
    goal_id = inputs.get("_goal_id", f"adhoc-{uuid.uuid4().hex}")
    step_id = inputs.get("_step_id", "step")
    path = output_dir / f"{goal_id}-{step_id}.wav"

    try:
        from audiocraft.models import MusicGen
        import torchaudio
        model = MusicGen.get_pretrained("facebook/musicgen-melody")
        waves = model.generate([prompt], duration=duration_s)
        torchaudio.save(str(path), waves[0].cpu(), model.sample_rate)
        return {"result": _with_artifact({"audio_path": str(path)}, path, goal_id)}
    except ImportError:
        return {"error": {"code": "MODEL_UNAVAILABLE", "message": "MusicGen (audiocraft) not installed"}}
    except Exception as e:
        return {"error": {"code": "GENERATION_FAILED", "message": f"MusicGen generation failed: {e}"}}


def _with_artifact(result: dict[str, Any], path: Path, goal_id: str | None) -> dict[str, Any]:
    art = get_registry().add(path, produced_by="music_gen/run", goal_id=goal_id or "ad-hoc")
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
