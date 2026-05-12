"""tools/sandbox/index.py — Execute code in agent-infra/sandbox."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from agent.config import CONFIG
from agent.session_manager import SessionDead, SessionError, SessionNotFound, SandboxSession, get_sandbox_session_manager


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    operation = inputs.get("operation", "")
    if operation not in ("code_execute", "jupyter_kernels_list", "file_upload", "file_download"):
        return {"error": {"code": "INVALID_OPERATION", "message": f"Unknown operation: {operation}"}}

    base_url = CONFIG.sandbox_url
    timeout_s = inputs.get("timeout_s", 60)
    session: SandboxSession | None = None

    try:
        import httpx
    except ImportError:
        return {"error": {"code": "SANDBOX_UNREACHABLE", "message": "httpx not installed"}}

    try:
        if operation == "code_execute":
            session = _resolve_session(inputs)
            code = inputs.get("code", "")
            language = inputs.get("language", "python")
            payload = {"code": code, "language": language, "timeout": timeout_s}
            if session:
                payload["cwd"] = session.workspace_path
            resp = httpx.post(
                f"{base_url}/v1/code/execute",
                json=payload,
                timeout=timeout_s + 10,
            )
            if resp.status_code >= 500:
                return {"error": {"code": "SANDBOX_UNREACHABLE", "message": f"Sandbox returned {resp.status_code}"}}
            data = resp.json()
            # New API format: response has success/data wrapper
            if data.get("success"):
                inner = data.get("data", {})
                stdout = inner.get("stdout", "") or ""
                stderr = inner.get("stderr", "") or ""
                # Extract text from outputs for richer stdout
                for out in inner.get("outputs", []):
                    if out.get("output_type") == "stream" and out.get("name") == "stdout":
                        stdout = (stdout or "") + (out.get("text", "") or "")
                return _with_session_id({
                    "result": {
                        "stdout": stdout,
                        "stderr": stderr,
                        "exit_code": inner.get("exit_code", 0) or 0,
                        "artifacts": inner.get("artifacts", []),
                    }
                }, session)
            # Error response
            return {"error": {"code": "EXECUTION_ERROR", "message": data.get("message", "Unknown error"), "details": data.get("data", {})}}

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
            session = _resolve_session(inputs)
            if session:
                destination = _scope_sandbox_path(session.workspace_path, destination)
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
            return _with_session_id(
                {"result": {"artifacts": [{"name": Path(file_path).name, "path": data.get("path", destination)}]}},
                session,
            )

        elif operation == "file_download":
            file_path = inputs.get("file", "")
            session = _resolve_session(inputs)
            if session:
                file_path = _scope_sandbox_path(session.workspace_path, file_path)
            resp = httpx.get(f"{base_url}/v1/files", params={"path": file_path}, timeout=timeout_s)
            if resp.status_code >= 500:
                return {"error": {"code": "SANDBOX_UNREACHABLE", "message": f"Sandbox returned {resp.status_code}"}}
            fd, local_path = tempfile.mkstemp(suffix=Path(file_path).suffix)
            os.close(fd)
            Path(local_path).write_bytes(resp.content)
            # Register downloaded file as artifact
            goal_id = inputs.get("goal_id")
            try:
                from agent.artifact_registry import get_registry
                art = get_registry().add(Path(local_path), produced_by="sandbox/file_download", goal_id=goal_id or "ad-hoc")
                artifact_data = {
                    "name": Path(file_path).name,
                    "path": str(local_path),
                    "artifact_id": art.id,
                    "artifact": {
                        "id": art.id,
                        "path": art.path,
                        "kind": art.kind,
                        "media_type": art.media_type,
                        "size_bytes": art.size_bytes,
                        "content_hash": art.content_hash,
                    },
                }
            except Exception:
                artifact_data = {"name": Path(file_path).name, "path": str(local_path)}
            return _with_session_id(
                {"result": {"artifacts": [artifact_data]}},
                session,
            )

    except SessionNotFound as exc:
        return {"error": {"code": "SESSION_NOT_FOUND", "message": str(exc)}}
    except SessionDead as exc:
        return {"error": {"code": "SESSION_DEAD", "message": str(exc)}}
    except SessionError as exc:
        return {"error": {"code": "SESSION_ERROR", "message": str(exc)}}
    except httpx.ConnectError:
        return {"error": {"code": "SANDBOX_UNREACHABLE", "message": f"Cannot connect to sandbox at {base_url}"}}
    except httpx.TimeoutException:
        return {"error": {"code": "TIMEOUT", "message": f"Request timed out after {timeout_s}s"}}
    except Exception as e:
        return {"error": {"code": "SANDBOX_UNREACHABLE", "message": str(e)}}


def _resolve_session(inputs: dict[str, Any]) -> SandboxSession | None:
    if "session_id" in inputs and inputs["session_id"] is None:
        return None

    manager = get_sandbox_session_manager()
    session_id = inputs.get("session_id")
    if session_id:
        return manager.attach(str(session_id))
    return manager.create(goal_id=inputs.get("goal_id"))


def _with_session_id(result: dict[str, Any], session: SandboxSession | None) -> dict[str, Any]:
    if session and "result" in result:
        result["result"]["session_id"] = session.session_id
    return result


def _scope_sandbox_path(workspace_path: str, requested_path: str) -> str:
    relative = requested_path.lstrip("/") or Path(requested_path).name
    if relative.startswith("workspace/"):
        relative = relative.removeprefix("workspace/")
    return f"{workspace_path}/{relative}"


if __name__ == "__main__":
    import json
    import sys

    payload = json.loads(sys.stdin.read())
    print(json.dumps(run(payload)))
