"""Unit tests for deliverables tool."""
from pathlib import Path

from tools.deliverables.index import run


def test_minimal_md_only(tmp_path):
    result = run({
        "title": "Test Report",
        "sections": [{"heading": "Intro", "body": "Hello world"}],
        "formats": ["md"],
    })
    assert "result" in result
    artifacts = result["result"]["artifacts"]
    assert len(artifacts) == 1
    assert artifacts[0]["format"] == "md"
    assert Path(artifacts[0]["path"]).exists()
    content = Path(artifacts[0]["path"]).read_text()
    assert "# Test Report" in content
    assert "Intro" in content


def test_full_set(tmp_path):
    result = run({
        "title": "Full Report",
        "sections": [{"heading": "Section 1", "body": "Content 1"}],
        "formats": ["md", "pdf", "xlsx", "pptx"],
    })
    assert "result" in result
    formats = {a["format"] for a in result["result"]["artifacts"]}
    assert {"md", "pdf", "xlsx", "pptx"}.issubset(formats)
    for a in result["result"]["artifacts"]:
        assert Path(a["path"]).exists()
        assert a["size_bytes"] > 0


def test_invalid_format_rejected(tmp_path):
    result = run({
        "title": "Test",
        "sections": [],
        "formats": ["xyzzy"],
    })
    assert result.get("error", {}).get("code") == "INVALID_FORMAT"


def test_with_table_data(tmp_path):
    result = run({
        "title": "Table Report",
        "sections": [{"heading": "Data", "body": "See table below"}],
        "table_data": [["Name", "Score"], ["Alice", "95"], ["Bob", "88"]],
        "formats": ["md", "csv"],
    })
    assert "result" in result
    formats = {a["format"] for a in result["result"]["artifacts"]}
    assert {"md", "csv"}.issubset(formats)
    csv_path = next(a["path"] for a in result["result"]["artifacts"] if a["format"] == "csv")
    content = Path(csv_path).read_text()
    assert "Alice" in content


def test_with_chart_spec(tmp_path):
    result = run({
        "title": "Chart Report",
        "sections": [{"heading": "Analysis", "body": "See chart"}],
        "chart_spec": {"Browser": 95, "Research": 88, "Apps": 76},
        "formats": ["md", "png"],
    })
    assert "result" in result
    formats = {a["format"] for a in result["result"]["artifacts"]}
    assert "png" in formats
    png_artifact = next(a for a in result["result"]["artifacts"] if a["format"] == "png")
    assert png_artifact["size_bytes"] > 0


def test_empty_sections(tmp_path):
    result = run({
        "title": "Empty Report",
        "sections": [],
        "formats": ["md"],
    })
    assert "result" in result
    assert len(result["result"]["artifacts"]) == 1
