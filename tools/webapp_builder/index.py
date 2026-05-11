"""tools/webapp_builder/index.py — Build web apps via bolt.diy subprocess."""
from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    prompt = inputs.get("prompt", "")
    if not prompt:
        return {"error": {"code": "INVALID_INPUT", "message": "Missing 'prompt' parameter"}}

    output_dir = inputs.get("output_dir", "")
    if not output_dir:
        outputs_base = Path(os.environ.get("RASPUTIN_OMNITOOL_OUTPUTS_DIR", "outputs"))
        outputs_base.mkdir(parents=True, exist_ok=True)
        output_dir = str(outputs_base / f"webapp-{uuid.uuid4().hex[:8]}")

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    try:
        # Test bolt availability
        subprocess.run(
            ["npx", "bolt", "--version"], capture_output=True, timeout=15
        )
    except FileNotFoundError:
        return {"error": {"code": "BOLT_NOT_INSTALLED", "message": "bolt.diy not found. Install: npm install -g @bolt.diy/cli"}}
    except subprocess.TimeoutExpired:
        return {"error": {"code": "TIMEOUT", "message": "bolt version check timed out"}}

    # Write prompt to file for bolt
    prompt_path = Path(output_dir) / "prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")

    cmd = [
        "npx", "bolt", "build",
        "--prompt", str(prompt_path),
        "--output", output_dir,
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600,
            cwd=output_dir
        )
        if result.returncode != 0:
            return {"error": {"code": "BOLT_FAILED", "message": f"bolt failed: {result.stderr.strip()}"}}

        return {
            "result": {
                "path": output_dir,
                "output": result.stdout.strip() if result.stdout else "",
            }
        }

    except subprocess.TimeoutExpired:
        return {"error": {"code": "TIMEOUT", "message": "bolt timed out after 600s"}}
    except Exception as e:
        return {"error": {"code": "BOLT_FAILED", "message": str(e)}}


if __name__ == "__main__":
    import json, sys
    payload = json.loads(sys.stdin.read())
    print(json.dumps(run(payload)))
