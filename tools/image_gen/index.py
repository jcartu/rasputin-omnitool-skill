"""tools/image_gen/index.py — Generate images via ComfyUI."""
from __future__ import annotations
import uuid
from pathlib import Path
from typing import Any

from agent.config import CONFIG


def _build_workflow(prompt: str, style: str, aspect_ratio: str) -> dict:
    """Build a minimal but valid ComfyUI workflow for image generation.

    This creates a basic SDXL/FLUX-compatible workflow with:
    - CheckpointLoaderSimple for the model
    - CLIPTextEncode nodes for positive/negative prompts
    - EmptyLatentImage for the latent space
    - KSampler for the actual sampling
    - VAEDecode for decoding to pixel space
    - SaveImage for output

    The workflow is intentionally minimal and relies on ComfyUI having
    a default checkpoint loaded. For production use, you'd want to
    specify the exact checkpoint and sampler.
    """
    # Map aspect ratio to width/height
    aspect_map = {
        "16:9": (1024, 576),
        "9:16": (576, 1024),
        "1:1": (768, 768),
        "4:3": (1024, 768),
        "3:4": (768, 1024),
    }
    width, height = aspect_map.get(aspect_ratio, (1024, 768))

    # Build the enhanced prompt with style
    enhanced_prompt = f"{prompt}, {style} style, high quality, detailed"
    negative_prompt = "blurry, low quality, distorted, deformed, ugly, bad anatomy"

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
                "ckpt_name": "model.safetensors",
            },
            "_meta": {"title": "Load Checkpoint"},
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
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1,
            },
            "_meta": {"title": "Empty Latent Image"},
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
            "class_type": "SaveImage",
            "inputs": {
                "images": ["8", 0],
                "filename_prefix": "image_gen",
            },
            "_meta": {"title": "Save Image"},
        },
    }


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    prompt = inputs.get("prompt", "")
    style = inputs.get("style", "photorealistic")
    aspect_ratio = inputs.get("aspect_ratio", "16:9")

    if not prompt:
        return {"error": {"code": "WORKFLOW_FAILED", "message": "Empty prompt"}}

    output_dir = Path(CONFIG.outputs_dir) / "images"
    output_dir.mkdir(parents=True, exist_ok=True)
    goal_id = inputs.get("_goal_id", f"adhoc-{uuid.uuid4().hex}")
    step_id = inputs.get("_step_id", "step")
    path = output_dir / f"{goal_id}-{step_id}.png"

    try:
        import httpx

        comfy_url = "http://127.0.0.1:8188"

        # Check ComfyUI reachable
        httpx.get(comfy_url, timeout=5)

        # Build proper ComfyUI workflow and submit
        workflow = _build_workflow(prompt, style, aspect_ratio)
        resp = httpx.post(f"{comfy_url}/prompt", json={"prompt": workflow}, timeout=300)
        if resp.status_code != 200:
            return {"error": {"code": "WORKFLOW_FAILED", "message": f"ComfyUI returned {resp.status_code}"}}

        prompt_id = resp.json().get("prompt_id")
        if not prompt_id:
            return {"error": {"code": "WORKFLOW_FAILED", "message": "No prompt_id returned"}}

        # Poll for completion
        for _ in range(300):
            time.sleep(1)
            history = httpx.get(f"{comfy_url}/history/{prompt_id}", timeout=10)
            if history.status_code == 200 and prompt_id in history.json():
                # Extract image from the SaveImage node (node ID "9")
                outputs = history.json()[prompt_id].get("outputs", {})
                save_node = outputs.get("9", {})
                images = save_node.get("images", [])
                if images and images[0].get("filename"):
                    filename = images[0]["filename"]
                    subfolder = images[0].get("subfolder", "")
                    full_path = f"{subfolder}/{filename}" if subfolder else filename
                    # Download image with timeout
                    download_resp = httpx.get(
                        f"{comfy_url}/view?filename={filename}&subfolder={subfolder}&type=output",
                        timeout=30,
                    )
                    if download_resp.status_code == 200:
                        path.write_bytes(download_resp.content)
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
