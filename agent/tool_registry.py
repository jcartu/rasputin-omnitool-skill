"""Tool registry — auto-discovers tools from tools/<name>/ via per-tool manifests."""
from __future__ import annotations

import importlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from jsonschema import validate, ValidationError

from agent.observability import observe

TOOLS_DIR = Path(__file__).parent.parent / "tools"
SCHEMA_PATH = Path(__file__).parent / "schemas" / "tool_manifest.schema.json"


@dataclass
class BackendStatus:
    name: str
    available: bool
    message: str = ""


@dataclass
class ToolDefinition:
    name: str
    version: str
    description: str
    schema: dict
    run: Callable[[dict], dict]
    source_dir: Path
    available: bool = True
    backend_statuses: list[BackendStatus] = field(default_factory=list)
    invalid_reason: Optional[str] = None


def _invalid_tool_runner(reason: str):
    def _runner(_inputs: dict) -> dict:
        return {"error": {"code": "INVALID_TOOL", "message": reason}}
    return _runner


def discover_tools(tools_dir: Path = TOOLS_DIR) -> dict[str, ToolDefinition]:
    """Walk tools_dir, load each tool that has a manifest.json + index.py."""
    schema = json.loads(SCHEMA_PATH.read_text())
    tools: dict[str, ToolDefinition] = {}

    for tool_dir in sorted(tools_dir.iterdir()):
        if not tool_dir.is_dir() or tool_dir.name.startswith("_") or tool_dir.name == "__pycache__":
            continue

        manifest_path = tool_dir / "manifest.json"
        index_path = tool_dir / "index.py"

        if not manifest_path.exists():
            continue
        if not index_path.exists():
            tools[tool_dir.name] = ToolDefinition(
                name=tool_dir.name, version="0.0.0", description="", schema={},
                run=_invalid_tool_runner("missing index.py"),
                source_dir=tool_dir, available=False,
                invalid_reason="missing index.py",
            )
            continue

        try:
            manifest = json.loads(manifest_path.read_text())
            validate(manifest, schema)
        except (json.JSONDecodeError, ValidationError) as exc:
            tools[tool_dir.name] = ToolDefinition(
                name=tool_dir.name, version="0.0.0", description="", schema={},
                run=_invalid_tool_runner(str(exc)),
                source_dir=tool_dir, available=False,
                invalid_reason=f"manifest invalid: {exc}",
            )
            continue

        if manifest["name"] != tool_dir.name:
            tools[tool_dir.name] = ToolDefinition(
                name=tool_dir.name, version=manifest.get("version", "0.0.0"),
                description=manifest.get("description", ""), schema=manifest,
                run=_invalid_tool_runner("name mismatch"),
                source_dir=tool_dir, available=False,
                invalid_reason=f"manifest name '{manifest['name']}' != dir name '{tool_dir.name}'",
            )
            continue

        try:
            module = importlib.import_module(f"tools.{tool_dir.name}.index")
            run_callable = getattr(module, "run", None)
            if not callable(run_callable):
                raise AttributeError("module has no callable run()")
        except Exception as exc:
            tools[tool_dir.name] = ToolDefinition(
                name=tool_dir.name, version=manifest["version"],
                description=manifest["description"], schema=manifest,
                run=_invalid_tool_runner(str(exc)),
                source_dir=tool_dir, available=False,
                invalid_reason=f"import failed: {exc}",
            )
            continue

        tools[tool_dir.name] = ToolDefinition(
            name=manifest["name"],
            version=manifest["version"],
            description=manifest["description"],
            schema=manifest,
            # Auto-wrap with @observe for Langfuse tracing
            run=observe(f"tool.{manifest['name']}")(run_callable),
            source_dir=tool_dir,
            available=True,
        )

    return tools


def probe_backends(tools: dict[str, ToolDefinition]) -> dict[str, ToolDefinition]:
    """For each tool with declared backends, probe their health URLs."""
    import httpx
    for tool in tools.values():
        backends = tool.schema.get("backends", [])
        if not backends:
            continue
        statuses: list[BackendStatus] = []
        any_required_down = False
        for backend in backends:
            url = backend.get("health_url")
            timeout = backend.get("health_timeout_s", 3)
            required = backend.get("required", True)
            try:
                resp = httpx.get(url, timeout=timeout)
                ok = resp.status_code == 200
                msg = "" if ok else f"http {resp.status_code}"
            except Exception as exc:
                ok = False
                msg = str(exc)
            statuses.append(BackendStatus(name=backend["name"], available=ok, message=msg))
            if not ok and required:
                any_required_down = True
        tool.backend_statuses = statuses
        if any_required_down:
            tool.available = False
    return tools


def load_tools() -> dict[str, Callable]:
    """One-shot: discover + probe + return callable dict (backward compat).

    Returns dict[str, Callable] for the executor's tool dispatch.
    """
    discovered = probe_backends(discover_tools())
    # Backward compat: return dict[str, Callable] as executor expects
    return {name: tool.run for name, tool in discovered.items()}


def load_tool_definitions() -> dict[str, ToolDefinition]:
    """One-shot: discover + probe + return full ToolDefinition dict."""
    return probe_backends(discover_tools())


def load_tool_metadata() -> list[dict]:
    """Load tool metadata for the planner (name + description)."""
    tools = discover_tools()
    return [
        {"name": t.name, "description": t.description}
        for t in tools.values()
    ]
