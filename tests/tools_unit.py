"""Skipped placeholder tests for tool scaffolds."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="PHASE-2 scaffold only; tool bodies wire in later phases")


def test_catalog_tool_placeholder() -> None:
    pass


def test_docling_tool_placeholder() -> None:
    pass


def test_crawl4ai_tool_placeholder() -> None:
    pass


def test_sandbox_tool_placeholder() -> None:
    pass


def test_browser_tool_placeholder() -> None:
    pass


def test_deliverables_tool_placeholder() -> None:
    pass


def test_tts_tool_placeholder() -> None:
    pass


def test_stt_tool_placeholder() -> None:
    pass


def test_image_gen_tool_placeholder() -> None:
    pass


def test_video_gen_tool_placeholder() -> None:
    pass


def test_music_gen_tool_placeholder() -> None:
    pass


def test_memory_tool_placeholder() -> None:
    pass
