"""tools/sandbox/index.py — Execute code in agent-infra/sandbox."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from agent.config import CONFIG


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    operation = inputs.get("operation", "")
    if operation not in ("code_execute", "jupyter_kernels_list", "file_upload", "file_download"):
        return {"error": {"code": "INVALID_OPERATION", "message": f"Unknown operation: {operation}"}}

    base_url = CONFIG.sandbox_url
    timeout_s = inputs.get("timeout_s", 60)

    try:
        import httpx
    except ImportError:
        return {"error": {"code": "SANDBOX_UNREACHABLE", "message": "httpx not installed"}}

    try:
        if operation == "code_execute":
            code = inputs.get("code", "")
            language = inputs.get("language", "python")
            resp = httpx.post(
                f"{base_url}/v1/code/execute",
                json={"code": code, "language": language, "timeout": timeout_s},
                timeout=timeout_s + 10,
            )
            if resp.status_code >= 500:
                return {"error": {"code": "SANDBOX_UNREACHABLE", "message": f"Sandbox returned {resp.status_code}"}}
            data = resp.json()
            return {
                "result": {
                    "stdout": data.get("stdout", ""),
                    "stderr": data.get("stderr", ""),
                    "exit_code": data.get("exit_code", 0),
                    "artifacts": data.get("artifacts", []),
                }
            }

        elif operation == "jupyter_kernels_list":
            resp = httpx.get(f"{base_url}/v1/jupyter/kernelspecs", timeout=timeout_s)
            if resp.status_code >= 500:
                return {"error": {"code": "SANDBOX_UNREACHABLE", "message": f"Sandbox returned {resp.status_code}"}}
            data = resp.json()
            kernels = data.get("kernelspecs", data.get("names", []))
            return {"result": {"artifacts": [{"name": k} for k in kernels]}}

        elif operation == "file_upload":
            file_path = inputs.get("file", "")
            destination = inputs.get("destination", "/workspace/upload")
            from tools.docling._allowed_paths import is_allowed
            if not is_allowed(Path(file_path)):
                return {"error": {"code": "OUTSIDE_ALLOWED_PATH", "message": f"Path outside allowed volumes: {file_path}"}}
            if not Path(file_path).exists():
                return {"error": {"code": "FILE_NOT_FOUND", "message": f"File not found: {file_path}"}}
            with open(file_path, "rb") as f:
                resp = httpx.post(
                    f"{base_url}/v1/files",
                    files={"file": (Path(file_path).name, f, "application/octet-stream")},
                    data={"destination": destination},
                    timeout=timeout_s + 10,
                )
            if resp.status_code >= 500:
                return {"error": {"code": "SANDBOX_UNREACHABLE", "message": f"Sandbox returned {resp.status_code}"}}
            data = resp.json()
            return {"result": {"artifacts": [{"name": Path(file_path).name, "path": data.get("path", destination)}]}}

        elif operation == "file_download":
            file_path = inputs.get("file", "")
            resp = httpx.get(f"{base_url}/v1/files", params={"path": file_path}, timeout=timeout_s)
            if resp.status_code >= 500:
                return {"error": {"code": "SANDBOX_UNREACHABLE", "message": f"Sandbox returned {resp.status_code}"}}
            fd, local_path = tempfile.mkstemp(suffix=Path(file_path).suffix)
            os.close(fd)
            Path(local_path).write_bytes(resp.content)
            return {"result": {"artifacts": [{"name": Path(file_path).name, "path": str(local_path)}]}}

    except httpx.ConnectError:
        return {"error": {"code": "SANDBOX_UNREACHABLE", "message": f"Cannot connect to sandbox at {base_url}"}}
    except httpx.TimeoutException:
        return {"error": {"code": "TIMEOUT", "message": f"Request timed out after {timeout_s}s"}}
    except Exception as e:
        return {"error": {"code": "SANDBOX_UNREACHABLE", "message": str(e)}}


if __name__ == "__main__":
    import json, sys

    payload = json.loads(sys.stdin.read())
    print(json.dumps(run(payload)))
