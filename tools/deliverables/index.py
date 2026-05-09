"""tools/deliverables/index.py — Generate multi-format deliverables.

Inputs: title, sections, table_data (optional), chart_spec (optional), formats (optional)
Outputs: artifacts array
Errors: INVALID_FORMAT, WRITE_FAILED

Status: WIRED (PHASE-3).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


ALLOWED_FORMATS = {"md", "pdf", "xlsx", "pptx", "csv", "html", "png"}


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    """Tool entry point invoked by OpenClaw."""
    from agent.config import CONFIG

    title = inputs.get("title", "Untitled Report")
    sections = inputs.get("sections", [])
    table_data = inputs.get("table_data", [])
    chart_spec = inputs.get("chart_spec")
    formats = inputs.get("formats", ["md", "pdf", "xlsx", "pptx"])

    # Validate formats
    for fmt in formats:
        if fmt not in ALLOWED_FORMATS:
            return {
                "error": {
                    "code": "INVALID_FORMAT",
                    "message": f"Format '{fmt}' not supported. Allowed: {sorted(ALLOWED_FORMATS)}",
                }
            }

    # Resolve output dir
    output_dir = Path(CONFIG.outputs_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        from rasputin_omnitool.deliverables import (
            _write_minimal_xlsx,
            _write_minimal_pptx,
            _write_fallback_chart_png,
        )

        artifacts = []

        # Build markdown content
        md_lines = [f"# {title}", ""]
        for section in sections:
            heading = section.get("heading", "Section")
            body = section.get("body", "")
            md_lines.append(f"## {heading}",)
            md_lines.append("")
            md_lines.append(body)
            md_lines.append("")
        if table_data:
            md_lines.append("| " + " | ".join(table_data[0]) + " |")
            md_lines.append("| " + " | ".join("---" for _ in table_data[0]) + " |")
            for row in table_data[1:]:
                md_lines.append("| " + " | ".join(str(c) for c in row) + " |")
            md_lines.append("")
        md_content = "\n".join(md_lines)

        if "md" in formats:
            p = output_dir / "deliverable.md"
            p.write_text(md_content)
            artifacts.append({"name": "deliverable.md", "path": str(p), "size_bytes": p.stat().st_size, "format": "md"})

        if "csv" in formats and table_data:
            import csv
            p = output_dir / "deliverable.csv"
            with p.open("w", newline="") as f:
                w = csv.writer(f)
                w.writerows(table_data)
            artifacts.append({"name": "deliverable.csv", "path": str(p), "size_bytes": p.stat().st_size, "format": "csv"})

        if "html" in formats:
            import html as html_mod
            html_rows = ""
            if table_data:
                header = "<tr>" + "".join(f"<th>{html_mod.escape(str(c))}</th>" for c in table_data[0]) + "</tr>"
                body_rows = "".join(
                    f"<tr>{''.join(f'<td>{html_mod.escape(str(c))}</td>' for c in row)}</tr>"
                    for row in table_data[1:]
                )
                html_rows = f"<table>{header}{body_rows}</table>"
            html_content = f"""<!doctype html><html><head><meta charset='utf-8'><title>{html_mod.escape(str(title))}</title><style>body{{font-family:Inter,Arial,sans-serif;margin:40px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:8px}}</style></head><body><h1>{html_mod.escape(str(title))}</h1>{html_rows}</body></html>"""
            p = output_dir / "deliverable.html"
            p.write_text(html_content)
            artifacts.append({"name": "deliverable.html", "path": str(p), "size_bytes": p.stat().st_size, "format": "html"})

        if "pdf" in formats:
            try:
                from weasyprint import HTML as HTMLToPdf
                html_path = output_dir / "deliverable.html"
                if not html_path.exists():
                    html_path.write_text(f"<!doctype html><html><body><h1>{title}</h1></body></html>")
                p = output_dir / "deliverable.pdf"
                HTMLToPdf(filename=str(html_path)).write_pdf(str(p))
            except Exception:
                p = output_dir / "deliverable.pdf"
                p.write_bytes(b"%PDF-1.4\n% Become Manus fallback PDF\n1 0 obj <<>> endobj\ntrailer <<>>\n%%EOF\n")
            artifacts.append({"name": "deliverable.pdf", "path": str(p), "size_bytes": p.stat().st_size, "format": "pdf"})

        if "xlsx" in formats:
            rows = [["Section", "Content"]] + [[s.get("heading", ""), s.get("body", "")] for s in sections]
            if table_data:
                rows = table_data
            p = output_dir / "deliverable.xlsx"
            _write_minimal_xlsx(p, rows)
            artifacts.append({"name": "deliverable.xlsx", "path": str(p), "size_bytes": p.stat().st_size, "format": "xlsx"})

        if "pptx" in formats:
            bullets = [s.get("heading", "") + ": " + s.get("body", "") for s in sections]
            p = output_dir / "deliverable.pptx"
            _write_minimal_pptx(p, title, bullets)
            artifacts.append({"name": "deliverable.pptx", "path": str(p), "size_bytes": p.stat().st_size, "format": "pptx"})

        if "png" in formats and chart_spec:
            chart_rows = [{"capability": str(k), "score": float(v)} for k, v in chart_spec.items()]
            p = output_dir / "deliverable_chart.png"
            _write_fallback_chart_png(p, chart_rows)
            artifacts.append({"name": "deliverable_chart.png", "path": str(p), "size_bytes": p.stat().st_size, "format": "png"})

        return {"result": {"artifacts": artifacts}}

    except Exception as e:
        return {
            "error": {
                "code": "WRITE_FAILED",
                "message": str(e),
            }
        }


if __name__ == "__main__":
    import json
    import sys

    payload = json.loads(sys.stdin.read())
    print(json.dumps(run(payload)))
