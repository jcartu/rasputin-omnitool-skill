"""tools/image-gen/index.py — Generate images via ComfyUI."""
from __future__ import annotations
from pathlib import Path
from typing import Any

from agent.config import CONFIG


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    prompt = inputs.get("prompt", "")
    style = inputs.get("style", "photorealistic")
    aspect_ratio = inputs.get("aspect_ratio", "16:9")

    if not prompt:
        return {"error": {"code": "WORKFLOW_FAILED", "message": "Empty prompt"}}

    output_dir = Path(CONFIG.outputs_dir) / "images"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"image.png"

    try:
        import httpx
        comfy_url = "http://127.0.0.1:8188"
        # Check ComfyUI reachable
        httpx.get(comfy_url, timeout=5)
        # Build workflow and submit
        workflow = {"prompt": prompt, "style": style, "aspect_ratio": aspect_ratio}
        resp = httpx.post(f"{comfy_url}/prompt", json=workflow, timeout=300)
        if resp.status_code != 200:
            return {"error": {"code": "WORKFLOW_FAILED", "message": f"ComfyUI returned {resp.status_code}"}}
        prompt_id = resp.json().get("prompt_id")
        # Poll for completion
        for _ in range(300):
            import time
            time.sleep(1)
            history = httpx.get(f"{comfy_url}/history/{prompt_id}", timeout=10)
            if history.status_code == 200 and prompt_id in history.json():
                # Download image
                import urllib.request
                filename = history.json()[prompt_id].get("outputs", {}).get("0", {}).get("images", [{}])[0].get("filename")
                if filename:
                    urllib.request.urlretrieve(f"{comfy_url}/view?filename={filename}", str(path))
                    return {"result": {"image_path": str(path), "metadata": {"prompt": prompt, "style": style}}}
                break
        return {"error": {"code": "WORKFLOW_FAILED", "message": "Generation timed out"}}
    except httpx.ConnectError:
        return {"error": {"code": "COMFY_UNREACHABLE", "message": "ComfyUI not running"}}
    except Exception as e:
        return {"error": {"code": "WORKFLOW_FAILED", "message": str(e)}}


if __name__ == "__main__":
    import json, sys
    payload = json.loads(sys.stdin.read())
    print(json.dumps(run(payload)))
