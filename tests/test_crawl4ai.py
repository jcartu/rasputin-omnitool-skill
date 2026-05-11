"""Unit tests for crawl4ai tool."""
import os

from tools.crawl4ai.index import run


def test_rejects_file_url():
    result = run({"url": "file:///etc/passwd"})
    assert result.get("error", {}).get("code") == "FETCH_FAILED"


def test_rejects_ftp_url():
    result = run({"url": "ftp://example.com/file"})
    assert result.get("error", {}).get("code") == "FETCH_FAILED"


def test_rejects_loopback_by_default():
    result = run({"url": "http://127.0.0.1:8080"})
    assert result.get("error", {}).get("code") == "FETCH_FAILED"


def test_rejects_private_ip():
    result = run({"url": "http://10.0.0.1/admin"})
    assert result.get("error", {}).get("code") == "FETCH_FAILED"


def test_rejects_link_local():
    result = run({"url": "http://169.254.169.254/latest/meta-data/"})
    assert result.get("error", {}).get("code") == "FETCH_FAILED"


def test_allows_loopback_when_env_set():
    os.environ["RASPUTIN_OMNITOOL_ALLOW_LOOPBACK_CRAWL"] = "1"
    try:
        result = run({"url": "http://127.0.0.1:8080"})
        if "error" in result:
            assert "loopback" not in result["error"]["message"].lower()
            assert result["error"]["code"] != "FETCH_FAILED" or "loopback" not in result["error"]["message"].lower()
    finally:
        os.environ.pop("RASPUTIN_OMNITOOL_ALLOW_LOOPBACK_CRAWL", None)
