"""tools/video-gen/index.py — Generate short video via Wan 2.1."""
from __future__ import annotations
from pathlib import Path
from typing import Any

from agent.config import CONFIG


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    prompt = inputs.get("prompt", "")
    duration_s = min(inputs.get("duration_s", 5), 10)
    fps = inputs.get("fps", 24)

    if not prompt:
        return {"error": {"code": "GENERATION_FAILED", "message": "Empty prompt"}}

    output_dir = Path(CONFIG.outputs_dir) / "video"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"video.mp4"

    try:
        import httpx
        comfy_url = "http://127.0.0.1:8188"
        # Check ComfyUI reachable
        httpx.get(comfy_url, timeout=5)
        # Build Wan workflow and submit
        workflow = {"prompt": prompt, "duration_s": duration_s, "fps": fps}
        resp = httpx.post(f"{comfy_url}/prompt", json=workflow, timeout=600)
        if resp.status_code != 200:
            return {"error": {"code": "GENERATION_FAILED", "message": f"ComfyUI returned {resp.status_code}"}}
        prompt_id = resp.json().get("prompt_id")
        # Poll for completion (Wan takes 2-8 minutes)
        for _ in range(600):
            import time
            time.sleep(1)
            history = httpx.get(f"{comfy_url}/history/{prompt_id}", timeout=10)
            if history.status_code == 200 and prompt_id in history.json():
                # Download video
                import urllib.request
                filename = history.json()[prompt_id].get("outputs", {}).get("0", {}).get("videos", [{}])[0].get("filename")
                if filename:
                    urllib.request.urlretrieve(f"{comfy_url}/view?filename={filename}", str(path))
                    return {"result": {"video_path": str(path)}}
                break
        return {"error": {"code": "GENERATION_FAILED", "message": "Generation timed out"}}
    except httpx.ConnectError:
        return {"error": {"code": "WAN_UNAVAILABLE", "message": "ComfyUI not running"}}
    except Exception as e:
        return {"error": {"code": "GENERATION_FAILED", "message": str(e)}}


if __name__ == "__main__":
    import json, sys
    payload = json.loads(sys.stdin.read())
    print(json.dumps(run(payload)))
