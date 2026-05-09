"""tools/video-gen/index.py — Generate short video via Wan 2.1."""
from __future__ import annotations
import time
from pathlib import Path
from typing import Any

from agent.config import CONFIG


def _build_wan_workflow(prompt: str, duration_s: float, fps: int) -> dict:
    """Build a minimal but valid ComfyUI workflow for Wan 2.1 video generation.

    This creates a basic Wan 2.1 workflow with:
    - CheckpointLoaderSimple for the Wan 2.1 model
    - CLIPTextEncode nodes for positive/negative prompts
    - EmptyLatentVideo for the video latent space
    - KSampler for the actual sampling
    - VAEDecode for decoding to pixel space
    - SaveAnimatedWEBP/SaveImage for video output

    The workflow is intentionally minimal and relies on ComfyUI having
    Wan 2.1 installed. For production use, you'd want to specify the
    exact checkpoint and sampler.
    """
    # Calculate number of frames based on duration and fps
    # Wan 2.1 typically supports 5-16 seconds at 24fps
    num_frames = min(int(duration_s * fps), 240)  # Cap at 240 frames (10s at 24fps)

    # Build the enhanced prompt
    enhanced_prompt = f"{prompt}, high quality, smooth motion, detailed, cinematic"
    negative_prompt = "blurry, low quality, distorted, deformed, ugly, bad anatomy, flickering"

    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 42,
                "steps": 20,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["5", 0],
                "negative": ["6", 0],
                "latent_image": ["7", 0],
            },
            "_meta": {"title": "KSampler"},
        },
        "4": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": "wan2.1_t2v_1.3B.safetensors",
            },
            "_meta": {"title": "Load Wan 2.1 Checkpoint"},
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": enhanced_prompt,
                "clip": ["4", 1],
            },
            "_meta": {"title": "CLIP Text Encode (Prompt)"},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative_prompt,
                "clip": ["4", 1],
            },
            "_meta": {"title": "CLIP Text Encode (Negative)"},
        },
        "7": {
            "class_type": "EmptyLatentVideo",
            "inputs": {
                "width": 832,
                "height": 480,
                "length": num_frames,
                "batch_size": 1,
            },
            "_meta": {"title": "Empty Latent Video"},
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["3", 0],
                "vae": ["4", 2],
            },
            "_meta": {"title": "VAE Decode"},
        },
        "9": {
            "class_type": "SaveAnimatedWEBP",
            "inputs": {
                "images": ["8", 0],
                "filename_prefix": "wan_video",
                "fps": fps,
                "lossless": True,
                "quality": 95,
            },
            "_meta": {"title": "Save Animated WEBP"},
        },
    }


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    prompt = inputs.get("prompt", "")
    duration_s = min(inputs.get("duration_s", 5), 10)
    fps = inputs.get("fps", 24)

    if not prompt:
        return {"error": {"code": "GENERATION_FAILED", "message": "Empty prompt"}}

    output_dir = Path(CONFIG.outputs_dir) / "video"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"video.webp"

    try:
        import httpx

        comfy_url = "http://127.0.0.1:8188"

        # Check ComfyUI reachable
        httpx.get(comfy_url, timeout=5)

        # Build proper Wan 2.1 ComfyUI workflow and submit
        workflow = _build_wan_workflow(prompt, duration_s, fps)
        resp = httpx.post(f"{comfy_url}/prompt", json={"prompt": workflow}, timeout=600)
        if resp.status_code != 200:
            return {"error": {"code": "GENERATION_FAILED", "message": f"ComfyUI returned {resp.status_code}"}}

        prompt_id = resp.json().get("prompt_id")
        if not prompt_id:
            return {"error": {"code": "GENERATION_FAILED", "message": "No prompt_id returned"}}

        # Poll for completion (Wan takes 2-8 minutes)
        for _ in range(600):
            time.sleep(1)
            history = httpx.get(f"{comfy_url}/history/{prompt_id}", timeout=10)
            if history.status_code == 200 and prompt_id in history.json():
                # Extract video from the SaveAnimatedWEBP node (node ID "9")
                outputs = history.json()[prompt_id].get("outputs", {})
                save_node = outputs.get("9", {})
                images = save_node.get("images", [])
                if images and images[0].get("filename"):
                    filename = images[0]["filename"]
                    subfolder = images[0].get("subfolder", "")
                    # Download video with timeout
                    download_resp = httpx.get(
                        f"{comfy_url}/view?filename={filename}&subfolder={subfolder}&type=output",
                        timeout=60,
                    )
                    if download_resp.status_code == 200:
                        path.write_bytes(download_resp.content)
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
