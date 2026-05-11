"""tools/slides/index.py — Generate slides from Markdown via Marp CLI."""
from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path
from typing import Any


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    markdown = inputs.get("markdown", "")
    if not markdown:
        return {"error": {"code": "INVALID_INPUT", "message": "Missing 'markdown' parameter"}}

    output_format = inputs.get("format", "pdf")
    if output_format not in ("pdf", "html", "pptx"):
        return {"error": {"code": "INVALID_FORMAT", "message": f"Unsupported format: {output_format}"}}

    outputs_dir = Path(os.environ.get("RASPUTIN_OMNITOOL_OUTPUTS_DIR", "outputs"))
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # Write temp markdown
    md_path = outputs_dir / f"slides-{uuid.uuid4().hex[:8]}.md"
    md_path.write_text(markdown, encoding="utf-8")

    out_path = outputs_dir / f"slides-{uuid.uuid4().hex[:8]}.{output_format}"

    try:
        cmd = ["marp", "--format", output_format, "--output", str(out_path), str(md_path)]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            return {"error": {"code": "MARP_FAILED", "message": f"Marp failed: {result.stderr.strip()}"}}

        return {
            "result": {
                "path": str(out_path),
                "format": output_format,
            }
        }

    except FileNotFoundError:
        return {"error": {"code": "MARP_NOT_INSTALLED", "message": "Marp CLI not found. Install: npm install -g @marp-team/marp-cli"}}
    except subprocess.TimeoutExpired:
        return {"error": {"code": "TIMEOUT", "message": "Marp conversion timed out after 120s"}}
    except Exception as e:
        return {"error": {"code": "MARP_FAILED", "message": str(e)}}
    finally:
        # Clean up temp markdown
        if md_path.exists():
            md_path.unlink()


if __name__ == "__main__":
    import json, sys
    payload = json.loads(sys.stdin.read())
    print(json.dumps(run(payload)))
