"""tools/memory/index.py — Persist and retrieve episodic memory via RASPUTIN MCP."""
from __future__ import annotations
from typing import Any


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    operation = inputs.get("operation", "")
    if operation not in ("store", "retrieve", "search"):
        return {"error": {"code": "INVALID_OPERATION", "message": f"Unknown operation: {operation}"}}

    try:
        import httpx
        mcp_url = "http://127.0.0.1:8808"

        if operation == "store":
            content = inputs.get("content", "")
            tags = inputs.get("tags", [])
            memory_id = inputs.get("memory_id")
            resp = httpx.post(f"{mcp_url}/memory/store", json={"content": content, "tags": tags, "memory_id": memory_id}, timeout=30)
            return {"result": {"memory_id": resp.json().get("memory_id", "")}}

        elif operation == "retrieve":
            memory_id = inputs.get("memory_id", "")
            resp = httpx.get(f"{mcp_url}/memory/retrieve", params={"memory_id": memory_id}, timeout=30)
            return {"result": {"results": [resp.json()]}}

        elif operation == "search":
            query = inputs.get("query", "")
            k = inputs.get("k", 5)
            resp = httpx.get(f"{mcp_url}/memory/search", params={"query": query, "k": k}, timeout=30)
            return {"result": {"results": resp.json().get("results", [])}}

    except httpx.ConnectError:
        return {"error": {"code": "MCP_UNREACHABLE", "message": "RASPUTIN MCP not running"}}
    except Exception as e:
        return {"error": {"code": "MCP_UNREACHABLE", "message": str(e)}}


if __name__ == "__main__":
    import json, sys
    payload = json.loads(sys.stdin.read())
    print(json.dumps(run(payload)))
