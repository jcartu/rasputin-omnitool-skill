"""Tool registry — loads all tool run() functions from tools/."""
from __future__ import annotations

from importlib import import_module
from typing import Callable

TOOL_NAMES = [
    "catalog", "docling", "crawl4ai", "sandbox", "browser", "deliverables",
    "tts", "stt", "image-gen", "video-gen", "music-gen", "memory",
]


def load_tools() -> dict[str, Callable]:
    """Load all tool run() functions from tools/<name>/index.py."""
    tools = {}
    for name in TOOL_NAMES:
        mod_name = name.replace("-", "_")
        module = import_module(f"tools.{mod_name}.index")
        tools[name] = module.run
    return tools


def load_tool_metadata() -> list[dict]:
    """Load tool metadata from manifest.json for the planner."""
    import json
    from pathlib import Path

    manifest_path = Path("manifest.json")
    if manifest_path.exists():
        data = json.loads(manifest_path.read_text())
        return [
            {"name": t["name"], "description": t["description"]}
            for t in data.get("tools", [])
        ]
    return [{"name": n, "description": ""} for n in TOOL_NAMES]
