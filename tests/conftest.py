"""Collect PHASE-2 placeholder test files with brief-specified names."""
from __future__ import annotations

import pytest


def pytest_collect_file(file_path, parent):  # type: ignore[no-untyped-def]
    if file_path.name in {"tools_unit.py", "loop_integration.py"}:
        return pytest.Module.from_parent(parent, path=file_path)
    return None
