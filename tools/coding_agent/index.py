"""tools/coding_agent/index.py — Execute coding tasks via aider subprocess."""
from __future__ import annotations

import os
import subprocess
from typing import Any


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    task = inputs.get("task", "")
    if not task:
        return {"error": {"code": "INVALID_INPUT", "message": "Missing 'task' parameter"}}

    cwd = inputs.get("cwd", "")
    model = inputs.get("model", os.environ.get("RASPUTIN_OMNITOOL_PLANNER_MODEL", "gpt-oss-120b"))
    timeout_s = int(inputs.get("timeout_s", 300))

    try:
        # Test aider availability
        subprocess.run(
            ["aider", "--version"], capture_output=True, timeout=5
        )
    except FileNotFoundError:
        return {"error": {"code": "AIDER_NOT_INSTALLED", "message": "aider not found. Install: pip install aider-chat"}}
    except subprocess.TimeoutExpired:
        return {"error": {"code": "TIMEOUT", "message": "aider version check timed out"}}

    cmd = [
        "aider",
        "--no-auto-commits",
        "--yes-always",
        "--model", model,
        "--message", task,
    ]
    files = inputs.get("files", [])
    if not isinstance(files, list):
        return {"error": {"code": "INVALID_INPUT", "message": "'files' must be a list of paths"}}
    cmd.extend(files)

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_s,
            cwd=cwd or os.getcwd()
        )
        if result.returncode != 0:
            return {"error": {"code": "AIDER_FAILED", "message": f"aider failed: {result.stderr.strip()}"}}

        return {
            "result": {
                "output": result.stdout.strip(),
                "stderr": result.stderr.strip() if result.stderr else "",
            }
        }

    except subprocess.TimeoutExpired:
        return {"error": {"code": "TIMEOUT", "message": f"aider timed out after {timeout_s}s"}}
    except Exception as e:
        return {"error": {"code": "AIDER_FAILED", "message": str(e)}}


if __name__ == "__main__":
    import json
    import sys

    payload = json.loads(sys.stdin.read())
    print(json.dumps(run(payload)))
