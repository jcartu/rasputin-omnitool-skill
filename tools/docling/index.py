"""tools/docling/index.py — Parse documents into markdown using Docling."""
from __future__ import annotations
from pathlib import Path
from typing import Any


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    path_str = inputs.get("path")
    if not path_str:
        return {"error": {"code": "FILE_NOT_FOUND", "message": "No path provided"}}

    path = Path(path_str)
    if not path.exists():
        return {"error": {"code": "FILE_NOT_FOUND", "message": f"File not found: {path}"}}

    from tools.docling._allowed_paths import is_allowed
    if not is_allowed(path):
        return {"error": {"code": "OUTSIDE_ALLOWED_PATH", "message": f"Path outside allowed volumes: {path}"}}

    max_chars = inputs.get("max_chars", 100000)

    try:
        from docling.document_converter import DocumentConverter
        converter = DocumentConverter()
        result = converter.convert(str(path))
        markdown = result.document.export_to_markdown()
        if len(markdown) > max_chars:
            markdown = markdown[:max_chars] + "\n\n... [truncated]"
        return {
            "result": {
                "markdown": markdown,
                "metadata": {
                    "source": str(path),
                    "char_count": len(markdown),
                }
            }
        }
    except Exception as e:
        return {"error": {"code": "PARSE_FAILED", "message": str(e)}}


if __name__ == "__main__":
    import json
    import sys

    payload = json.loads(sys.stdin.read())
    print(json.dumps(run(payload)))
