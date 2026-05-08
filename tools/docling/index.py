"""tools/docling/index.py — TOOL CONTRACT

Inputs: see manifest.json
Outputs: see manifest.json
Errors: see manifest.json

Status: SCAFFOLD ONLY. Body wired in PHASE-{3 or 5}.
"""
from __future__ import annotations
from typing import Any


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    """Tool entry point invoked by OpenClaw.

    Returns a dict with either {"result": ...} on success or {"error": {...}} on failure.
    """
    return {
        "error": {
            "code": "NOT_IMPLEMENTED",
            "message": "Tool body is scaffolded but not yet wired. See sprint phase brief.",
        }
    }


if __name__ == "__main__":
    import json
    import sys

    payload = json.loads(sys.stdin.read())
    print(json.dumps(run(payload)))
