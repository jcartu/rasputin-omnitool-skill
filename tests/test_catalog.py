from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path("/home/josh/workspace/become-manus")))

from tools.catalog.index import run


def test_no_filter_returns_all() -> None:
    response = run({})

    assert "result" in response
    assert len(response["result"]["candidates"]) >= 28


def test_filter_by_capability() -> None:
    response = run({"capability": "browser_operator"})

    names = {candidate["name"] for candidate in response["result"]["candidates"]}
    assert "Playwright MCP" in names


def test_invalid_capability_returns_error() -> None:
    response = run({"capability": "no_such_capability"})

    assert response["error"]["code"] == "INVALID_CAPABILITY"


def test_filter_by_license() -> None:
    response = run({"license_only": ["MIT"]})

    assert "result" in response
    assert all("MIT" in candidate["license"] for candidate in response["result"]["candidates"])


def test_empty_match_returns_no_match_error() -> None:
    response = run({"license_only": ["MADE_UP_LICENSE"]})

    assert response["error"]["code"] == "NO_MATCH"
