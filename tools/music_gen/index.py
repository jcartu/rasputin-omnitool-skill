"""tools/music_gen/index.py — Generate music via MusicGen-Melody."""
from __future__ import annotations
from pathlib import Path
import uuid
from typing import Any

from agent.config import CONFIG


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
        return {"result": {"audio_path": str(path)}}
    except ImportError:
        return {"error": {"code": "MODEL_UNAVAILABLE", "message": "MusicGen (audiocraft) not installed"}}
    except Exception as e:
        return {"error": {"code": "GENERATION_FAILED", "message": f"MusicGen generation failed: {e}"}}


if __name__ == "__main__":
    import json, sys
    payload = json.loads(sys.stdin.read())
    print(json.dumps(run(payload)))
