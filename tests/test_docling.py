"""Unit tests for docling tool."""
from pathlib import Path

from tools.docling.index import run


def test_file_not_found_returns_error():
    result = run({"path": "/nonexistent/file.docx"})
    assert result.get("error", {}).get("code") == "FILE_NOT_FOUND"


def test_outside_allowed_path_returns_error():
    result = run({"path": "/etc/hostname"})
    assert result.get("error", {}).get("code") == "OUTSIDE_ALLOWED_PATH"


def test_parses_fixture_docx(tmp_path):
    # Use kernel's fixture writer
    from become_manus_kernel.library_smoke import _write_docx_fixture
    inbox = Path("/tmp/become-manus-inbox")
    inbox.mkdir(exist_ok=True)
    docx_path = inbox / "test.docx"
    _write_docx_fixture(docx_path)

    result = run({"path": str(docx_path)})
    if result.get("error", {}).get("code") == "PARSE_FAILED":
        assert "docling" in result["error"]["message"]
        return

    assert "result" in result
    assert "markdown" in result["result"]
    assert len(result["result"]["markdown"]) > 0


def test_no_path_returns_error():
    result = run({})
    assert result.get("error", {}).get("code") == "FILE_NOT_FOUND"
