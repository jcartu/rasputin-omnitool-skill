"""tools/coding_agent/index.py — Execute coding tasks via aider subprocess."""
from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path
from typing import Any


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    task = inputs.get("task", "")
    if not task:
        return {"error": {"code": "INVALID_INPUT", "message": "Missing 'task' parameter"}}

    repo_path = inputs.get("repo_path", "")
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

    # Build command
    cmd = [
        "aider",
        "--no-auto-commits",
        "--yes-always",
        "--model", model,
    ]
    if repo_path:
        cmd.extend(["--repo", repo_path])
    cmd.extend(["--message", task])

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_s,
            cwd=repo_path or os.getcwd()
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
    import json, sys
    payload = json.loads(sys.stdin.read())
    print(json.dumps(run(payload)))
