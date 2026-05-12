"""tools/memory/index.py — Persist and retrieve episodic memory via RASPUTIN MCP."""
from __future__ import annotations
from typing import Any


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    operation = inputs.get("operation", "")
    if operation not in ("store", "retrieve", "search"):
        return {"error": {"code": "INVALID_OPERATION", "message": f"Unknown operation: {operation}"}}

    # Input validation
    if operation == "store":
        content = inputs.get("content", "")
        if not content:
            return {"error": {"code": "INVALID_OPERATION", "message": "Empty content"}}
    elif operation == "retrieve":
        memory_id = inputs.get("memory_id", "")
        if not memory_id:
            return {"error": {"code": "INVALID_OPERATION", "message": "memory_id required for retrieve"}}
    elif operation == "search":
        query = inputs.get("query", "")
        if not query:
            return {"error": {"code": "INVALID_OPERATION", "message": "Empty query"}}

    try:
        import httpx
        mcp_url = "http://127.0.0.1:8808"

        if operation == "store":
            tags = inputs.get("tags", [])
            memory_id = inputs.get("memory_id")
            resp = httpx.post(f"{mcp_url}/memory/store", json={"content": content, "tags": tags, "memory_id": memory_id}, timeout=30)
            resp.raise_for_status()
            return {"result": {"memory_id": resp.json().get("memory_id", "")}}

        elif operation == "retrieve":
            resp = httpx.get(f"{mcp_url}/memory/retrieve", params={"memory_id": memory_id}, timeout=30)
            resp.raise_for_status()
            return {"result": {"results": [resp.json()]}}

        elif operation == "search":
            k = min(max(1, inputs.get("k", 5)), 100)
            resp = httpx.get(f"{mcp_url}/memory/search", params={"query": query, "k": k}, timeout=30)
            resp.raise_for_status()
            return {"result": {"results": resp.json().get("results", [])}}

    except httpx.ConnectError:
        return {"error": {"code": "MCP_UNREACHABLE", "message": "RASPUTIN MCP not running"}}
    except httpx.HTTPStatusError as e:
        return {"error": {"code": "MCP_UNREACHABLE", "message": f"MCP returned {e.response.status_code}: {e.response.text}"}}
    except Exception as e:
        return {"error": {"code": "MCP_UNREACHABLE", "message": str(e)}}


if __name__ == "__main__":
    import json
    import sys
    payload = json.loads(sys.stdin.read())
    print(json.dumps(run(payload)))
