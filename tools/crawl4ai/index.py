"""tools/crawl4ai/index.py — Crawl URLs and return LLM-friendly markdown."""

from __future__ import annotations

import asyncio
import os
from typing import Any
from urllib.parse import urlparse


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    url = inputs.get("url", "")
    timeout_s = inputs.get("timeout_s", 30)
    cache_mode = inputs.get("cache_mode", "default")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return {
            "error": {
                "code": "FETCH_FAILED",
                "message": f"Only http(s):// URLs allowed, got: {parsed.scheme}://",
            }
        }

    hostname = parsed.hostname or ""
    allow_loopback = os.environ.get("BMS_ALLOW_LOOPBACK_CRAWL", "0") == "1"
    if not allow_loopback and (
        hostname in ("localhost", "127.0.0.1", "::1")
        or hostname.startswith("10.")
        or hostname.startswith("192.168.")
        or hostname.startswith("172.")
    ):
        return {
            "error": {
                "code": "FETCH_FAILED",
                "message": f"Loopback/internal URL blocked: {hostname}. Set BMS_ALLOW_LOOPBACK_CRAWL=1 to allow.",
            }
        }

    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

        async def _crawl():
            async with AsyncWebCrawler(config=BrowserConfig(headless=True)) as crawler:
                result = await asyncio.wait_for(
                    crawler.arun(
                        url=url,
                        config=CrawlerRunConfig(
                            cache_mode=cache_mode,
                            bypass_cache=(cache_mode == "bypass"),
                        ),
                    ),
                    timeout=timeout_s,
                )
                return result

        result = asyncio.run(_crawl())
        return {
            "result": {
                "markdown": result.markdown or "",
                "title": result.title or "",
                "links": list(result.links.get("external", []))[:100],
            }
        }
    except asyncio.TimeoutError:
        return {"error": {"code": "TIMEOUT", "message": f"Crawl timed out after {timeout_s}s"}}
    except Exception as e:
        err_str = str(e).lower()
        if any(code in err_str for code in ("403", "429", "blocked", "forbidden")):
            return {"error": {"code": "BLOCKED", "message": str(e)}}
        return {"error": {"code": "FETCH_FAILED", "message": str(e)}}


if __name__ == "__main__":
    import json
    import sys

    payload = json.loads(sys.stdin.read())
    print(json.dumps(run(payload)))
