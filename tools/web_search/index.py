"""tools/web_search/index.py — Search the web via SearXNG."""
from __future__ import annotations

import os
import httpx
from typing import Any


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    query = inputs.get("query", "")
    if not query:
        return {"error": {"code": "INVALID_INPUT", "message": "Missing 'query' parameter"}}

    base_url = os.environ.get("RASPUTIN_OMNITOOL_SEARXNG_URL", "http://localhost:8080")
    max_results = int(inputs.get("max_results", 10))
    categories = inputs.get("categories", "general")
    time_range = inputs.get("time_range", "")
    language = inputs.get("language", "en")

    try:
        params = {
            "q": query,
            "format": "json",
            "categories": categories,
            "language": language,
            "pageno": 1,
        }
        if time_range:
            params["time_range"] = time_range

        resp = httpx.get(f"{base_url}/search", params=params, timeout=15)
        if resp.status_code >= 500:
            return {"error": {"code": "SEARXNG_UNREACHABLE", "message": f"SearXNG returned {resp.status_code}"}}

        data = resp.json()
        results = data.get("results", [])[:max_results]

        return {
            "result": {
                "query": query,
                "results": [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("content", ""),
                    }
                    for r in results
                ],
            }
        }

    except httpx.ConnectError:
        return {"error": {"code": "SEARXNG_UNREACHABLE", "message": f"Cannot connect to SearXNG at {base_url}"}}
    except httpx.TimeoutException:
        return {"error": {"code": "TIMEOUT", "message": "SearXNG request timed out"}}
    except Exception as e:
        return {"error": {"code": "SEARXNG_UNREACHABLE", "message": str(e)}}


if __name__ == "__main__":
    import json, sys
    payload = json.loads(sys.stdin.read())
    print(json.dumps(run(payload)))
