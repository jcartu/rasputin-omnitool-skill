"""tools/catalog/index.py — catalog tool implementation."""
from __future__ import annotations

import json
import sys
from typing import Any

from become_manus_kernel import CAPABILITIES, all_candidates, candidate_summary


def _error(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    """Return catalog candidates filtered by capability and/or license."""
    capability = inputs.get("capability")
    if capability is not None and capability not in CAPABILITIES:
        return _error(
            "INVALID_CAPABILITY",
            f"Unknown capability '{capability}'. Expected one of: {', '.join(sorted(CAPABILITIES))}.",
        )

    license_only = inputs.get("license_only")
    if license_only is not None and (
        not isinstance(license_only, list) or not all(isinstance(item, str) for item in license_only)
    ):
        return _error("INVALID_LICENSE_FILTER", "license_only must be a list of strings.")

    candidates = all_candidates()
    if capability is not None:
        candidates = [candidate for candidate in candidates if candidate["capability"] == capability]

    if license_only is not None:
        candidates = [candidate for candidate in candidates if candidate["license"] in license_only]

    if not candidates:
        return _error("NO_MATCH", "No catalog candidates match the requested filters.")

    return {"result": {"candidates": candidates, "summary": candidate_summary()}}


if __name__ == "__main__":
    payload = json.loads(sys.stdin.read())
    print(json.dumps(run(payload)))
