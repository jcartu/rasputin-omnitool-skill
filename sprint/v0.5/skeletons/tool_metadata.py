"""Skeleton for Phase 1: agent/tool_registry.load_tool_metadata().

Drop this into agent/tool_registry.py replacing the empty placeholder. Adjust
imports to the project's existing names. The TTL cache MUST be preserved.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock


# Cached metadata + TTL — re-probe at most every 30s.
_METADATA_CACHE: dict[str, list[dict]] = {}
_METADATA_CACHE_AT: dict[str, float] = {}
_METADATA_LOCK = Lock()
_METADATA_TTL_S = 30.0


def load_tool_metadata(include_unavailable: bool = False) -> list[dict]:
    """Return tool metadata for the planner and the ReAct executor.

    Each entry has:
        name: str
        version: str
        description: str
        inputs: dict          # JSON-schema-like, from manifest
        outputs: dict
        errors: list[str]
        tags: list[str]
        available: bool
        backend_statuses: list[{"name": str, "available": bool, "message": str}]
    """
    cache_key = "all" if include_unavailable else "available"

    with _METADATA_LOCK:
        cached_at = _METADATA_CACHE_AT.get(cache_key, 0.0)
        if time.monotonic() - cached_at < _METADATA_TTL_S and cache_key in _METADATA_CACHE:
            return _METADATA_CACHE[cache_key]

        # discover + probe; reuse the existing project helpers
        definitions = probe_backends(discover_tools())

        out: list[dict] = []
        for name, td in sorted(definitions.items()):
            manifest = td.schema or {}
            entry = {
                "name": td.name,
                "version": td.version,
                "description": td.description,
                "inputs": manifest.get("inputs", {}),
                "outputs": manifest.get("outputs", {}),
                "errors": manifest.get("errors", []),
                "tags": manifest.get("tags", []),
                "available": td.available,
                "backend_statuses": [
                    {"name": bs.name, "available": bs.available, "message": bs.message}
                    for bs in td.backend_statuses
                ],
            }
            if entry["available"] or include_unavailable:
                out.append(entry)

        _METADATA_CACHE[cache_key] = out
        _METADATA_CACHE_AT[cache_key] = time.monotonic()
        return out


def invalidate_metadata_cache() -> None:
    """Test hook — force re-probe on next load_tool_metadata() call."""
    with _METADATA_LOCK:
        _METADATA_CACHE.clear()
        _METADATA_CACHE_AT.clear()


# ----- helper for ReAct executor: OpenAI-style tool schemas -----

def to_openai_tool_schemas(metadata: list[dict]) -> list[dict]:
    """Convert our metadata list into OpenAI function-call schemas.

    The ReAct executor passes this directly to the chat completions API.
    """
    schemas: list[dict] = []
    for t in metadata:
        if not t["available"]:
            continue
        params = _inputs_to_json_schema(t["inputs"])
        schemas.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": _build_description(t),
                "parameters": params,
            },
        })
    return schemas


def _build_description(t: dict) -> str:
    base = t["description"].strip()
    tags = t.get("tags", [])
    errors = t.get("errors", [])
    tail = ""
    if tags:
        tail += f"\nTags: {', '.join(tags)}."
    if errors:
        tail += f"\nMay return these error codes: {', '.join(errors)}."
    return base + tail


def _inputs_to_json_schema(inputs: dict) -> dict:
    """Project's manifest input format → JSON schema 'parameters'.

    Manifest input shape (per-tool):
        {
          "field_name": {
            "type": "string"|"integer"|"number"|"boolean"|"array"|"object",
            "required": bool,
            "enum": [...],         # optional
            "items": {...},        # for array
            "description": "..."   # optional
          }, ...
        }
    """
    props: dict = {}
    required: list[str] = []
    for field_name, spec in inputs.items():
        prop: dict = {"type": spec.get("type", "string")}
        if "enum" in spec:
            prop["enum"] = spec["enum"]
        if "items" in spec:
            prop["items"] = spec["items"]
        if "description" in spec:
            prop["description"] = spec["description"]
        if "default" in spec:
            prop["default"] = spec["default"]
        props[field_name] = prop
        if spec.get("required"):
            required.append(field_name)
    return {
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False,
    }


# ----- placeholders to satisfy this skeleton standalone -----

@dataclass
class _BS:
    name: str
    available: bool
    message: str = ""

def discover_tools(): ...        # provided by existing tool_registry.py
def probe_backends(t): ...       # provided by existing tool_registry.py
