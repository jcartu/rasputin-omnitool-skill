"""Unit tests for docling tool."""
from pathlib import Path
import pytest

from tools.docling.index import run


def test_file_not_found_returns_error():
    result = run({"path": "/nonexistent/file.docx"})
    assert result.get("error", {}).get("code") == "FILE_NOT_FOUND"


def test_outside_allowed_path_returns_error():
    result = run({"path": "/etc/hostname"})
    assert result.get("error", {}).get("code") == "OUTSIDE_ALLOWED_PATH"


def test_no_path_returns_error():
    result = run({})
    assert result.get("error", {}).get("code") == "FILE_NOT_FOUND"


def test_parses_fixture_docx(tmp_path):
    # Use kernel's fixture writer if available, otherwise skip
    try:
        from become_manus_kernel.library_smoke import _write_docx_fixture
    except ImportError:
        pytest.skip("become_manus_kernel not available")

    try:
        from docling.document_converter import DocumentConverter
    except ImportError:
        pytest.skip("docling not installed")

    inbox = Path("/tmp/become-manus-inbox")
    inbox.mkdir(exist_ok=True)
    docx_path = inbox / "test.docx"
    _write_docx_fixture(docx_path)

    result = run({"path": str(docx_path)})
    assert "result" in result
    assert "markdown" in result["result"]
    assert len(result["result"]["markdown"]) > 0


def test_max_chars_truncation(tmp_path):
    try:
        from become_manus_kernel.library_smoke import _write_docx_fixture
    except ImportError:
        pytest.skip("become_manus_kernel not available")

    try:
        from docling.document_converter import DocumentConverter
    except ImportError:
        pytest.skip("docling not installed")

    inbox = Path("/tmp/become-manus-inbox")
    inbox.mkdir(exist_ok=True)
    docx_path = inbox / "test.docx"
    _write_docx_fixture(docx_path)

    result = run({"path": str(docx_path), "max_chars": 50})
    assert "result" in result
    # Should include truncation marker
    assert "[truncated]" in result["result"]["markdown"]
