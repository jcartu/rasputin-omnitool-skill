"""tools/mail/index.py — Send/receive email via Himalaya CLI."""
from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path
from typing import Any


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    operation = inputs.get("operation", "")
    if operation not in ("send", "list", "read"):
        return {"error": {"code": "INVALID_OPERATION", "message": f"Unknown operation: {operation}"}}

    try:
        # Test Himalaya availability
        subprocess.run(
            ["himalaya", "--version"], capture_output=True, timeout=5
        )
    except FileNotFoundError:
        return {"error": {"code": "HIMALAYA_NOT_INSTALLED", "message": "Himalaya CLI not found. Install: https://himalaya.email/"}}
    except subprocess.TimeoutExpired:
        return {"error": {"code": "TIMEOUT", "message": "Himalaya version check timed out"}}

    try:
        if operation == "send":
            return _send(inputs)
        elif operation == "list":
            return _list(inputs)
        elif operation == "read":
            return _read(inputs)

    except subprocess.TimeoutExpired:
        return {"error": {"code": "TIMEOUT", "message": "Himalaya operation timed out"}}
    except Exception as e:
        return {"error": {"code": "HIMALAYA_FAILED", "message": str(e)}}


def _send(inputs: dict[str, Any]) -> dict[str, Any]:
    to = inputs.get("to", "")
    subject = inputs.get("subject", "")
    body = inputs.get("body", "")
    if not to:
        return {"error": {"code": "INVALID_INPUT", "message": "Missing 'to' parameter"}}

    # Write body to temp file
    outputs_dir = Path(os.environ.get("RASPUTIN_OMNITOOL_OUTPUTS_DIR", "outputs"))
    outputs_dir.mkdir(parents=True, exist_ok=True)
    body_path = outputs_dir / f"mail-body-{uuid.uuid4().hex[:8]}.txt"
    body_path.write_text(body, encoding="utf-8")

    try:
        cmd = [
            "himalaya", "send",
            "--to", to,
            "--subject", subject,
        ]
        result = subprocess.run(
            cmd, input=body, capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            return {"error": {"code": "HIMALAYA_FAILED", "message": f"Himalaya send failed: {result.stderr.strip()}"}}

        return {"result": {"status": "sent", "to": to, "subject": subject}}
    finally:
        if body_path.exists():
            body_path.unlink()


def _list(inputs: dict[str, Any]) -> dict[str, Any]:
    folder = inputs.get("folder", "INBOX")
    limit = int(inputs.get("limit", 20))

    cmd = ["himalaya", "list", folder, "--limit", str(limit)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        return {"error": {"code": "HIMALAYA_FAILED", "message": f"Himalaya list failed: {result.stderr.strip()}"}}

    return {"result": {"folder": folder, "output": result.stdout.strip()}}


def _read(inputs: dict[str, Any]) -> dict[str, Any]:
    message_id = inputs.get("message_id", "")
    if not message_id:
        return {"error": {"code": "INVALID_INPUT", "message": "Missing 'message_id' parameter"}}

    cmd = ["himalaya", "read", message_id]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        return {"error": {"code": "HIMALAYA_FAILED", "message": f"Himalaya read failed: {result.stderr.strip()}"}}

    return {"result": {"message_id": message_id, "content": result.stdout}}


if __name__ == "__main__":
    import json, sys
    payload = json.loads(sys.stdin.read())
    print(json.dumps(run(payload)))
