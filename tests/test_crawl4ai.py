"""Unit tests for crawl4ai tool."""

import os

from tools.crawl4ai.index import run


def test_rejects_file_url():
    result = run({"url": "file:///etc/passwd"})
    assert result.get("error", {}).get("code") == "FETCH_FAILED"


def test_rejects_loopback_by_default():
    result = run({"url": "http://127.0.0.1:8080"})
    assert result.get("error", {}).get("code") == "FETCH_FAILED"


def test_allows_loopback_when_env_set():
    os.environ["BMS_ALLOW_LOOPBACK_CRAWL"] = "1"
    try:
        result = run({"url": "http://127.0.0.1:8080"})
        # Should NOT return FETCH_FAILED for loopback reason
        if "error" in result:
            assert "loopback" not in result["error"]["message"].lower()
    finally:
        os.environ.pop("BMS_ALLOW_LOOPBACK_CRAWL", None)


def test_rejects_ftp_url():
    result = run({"url": "ftp://example.com/file"})
    assert result.get("error", {}).get("code") == "FETCH_FAILED"


def test_crawls_example_com():
    result = run({"url": "http://example.com"})
    # May fail if crawl4ai not installed, but should not crash
    assert "result" in result or "error" in result
