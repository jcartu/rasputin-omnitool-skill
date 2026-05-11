"""tools/crawl4ai/index.py — Crawl URLs and return LLM-friendly markdown."""

from __future__ import annotations

import asyncio
import ipaddress
import os
import socket
from typing import Any
from urllib.parse import urlparse


def _is_blocked_host(hostname: str) -> tuple[bool, str]:
    """Return (blocked, reason) for SSRF protection.

    Blocks loopback, link-local, private, and unspecified addresses after DNS
    resolution. Catches both IPv4 and IPv6 ranges.
    """
    if not hostname:
        return True, "empty hostname"

    # Block by name first to avoid DNS lookups for obvious cases
    lowered = hostname.lower().strip("[]")
    if lowered in ("localhost", "ip6-localhost", "ip6-loopback"):
        return True, f"loopback name: {hostname}"

    # Resolve DNS to all candidate addresses; if ANY resolved IP is private,
    # link-local, loopback, or unspecified — block (DNS rebinding-safe).
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        return True, f"DNS resolution failed: {e}"

    for info in infos:
        addr = info[4][0]
        # Strip IPv6 zone identifiers (e.g. "fe80::1%eth0")
        addr = addr.split("%", 1)[0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_unspecified
            or ip.is_reserved
            or ip.is_multicast
        ):
            return True, f"non-public IP {ip} for host {hostname}"
    return False, ""


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
    allow_loopback = os.environ.get("RASPUTIN_OMNITOOL_ALLOW_LOOPBACK_CRAWL", "0") == "1"
    if not allow_loopback:
        blocked, reason = _is_blocked_host(hostname)
        if blocked:
            return {
                "error": {
                    "code": "FETCH_FAILED",
                    "message": f"Loopback/internal URL blocked ({reason}). Set RASPUTIN_OMNITOOL_ALLOW_LOOPBACK_CRAWL=1 to allow.",
                }
            }

    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig

        cache_mode_map = {
            "default": CacheMode.ENABLED,
            "bypass": CacheMode.BYPASS,
            "only": CacheMode.READ_ONLY,
        }
        resolved_cache_mode = cache_mode_map.get(cache_mode, CacheMode.ENABLED)

        async def _crawl():
            async with AsyncWebCrawler(config=BrowserConfig(headless=True)) as crawler:
                result = await asyncio.wait_for(
                    crawler.arun(
                        url=url,
                        config=CrawlerRunConfig(
                            cache_mode=resolved_cache_mode,
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
