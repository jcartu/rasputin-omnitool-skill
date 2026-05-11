#!/usr/bin/env python3
"""Regenerate the skill-level manifest.json from per-tool manifests.

Run before commit to keep manifest.json in sync with tools/<name>/manifest.json.
CI verifies the committed manifest.json byte-equals what this script generates.

Usage:
    python scripts/regenerate-skill-manifest.py       # write manifest.json
    python scripts/regenerate-skill-manifest.py --check  # compare without writing
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
TOOLS = sorted([d for d in (ROOT / "tools").iterdir() if d.is_dir() and not d.name.startswith("_")])

skill_manifest = {
    "schema_version": "2026.4",
    "name": "rasputin-omnitool-skill",
    "version": "0.4.0",
    "tools": [],
    "permissions": {
        "filesystem": ["read:./outputs", "write:./outputs"],
        "network": ["egress:*"],
        "subprocess": ["docker", "ffmpeg", "node", "npm"],
    },
    "models_required": [
        "Qwen3-27B (OpenCode Zen)",
        "Claude Opus 4.7 (Anthropic API)",
    ],
}

for tool_dir in TOOLS:
    manifest_path = tool_dir / "manifest.json"
    if not manifest_path.exists():
        continue
    tool_manifest = json.loads(manifest_path.read_text())
    skill_manifest["tools"].append({
        "name": tool_manifest["name"],
        "version": tool_manifest["version"],
        "description": tool_manifest["description"],
        "inputs": tool_manifest["inputs"],
        "outputs": tool_manifest["outputs"],
        "errors": tool_manifest["errors"],
        "status": tool_manifest.get("status", "available"),
    })

generated = json.dumps(skill_manifest, indent=2) + "\n"
target = ROOT / "manifest.json"

if "--check" in sys.argv:
    existing = target.read_text()
    if existing == generated:
        print("OK: manifest.json is in sync")
        sys.exit(0)
    else:
        print("ERROR: manifest.json out of sync with tools/*/manifest.json")
        print("Run: python scripts/regenerate-skill-manifest.py")
        sys.exit(1)

target.write_text(generated)
print(f"wrote {target} with {len(skill_manifest['tools'])} tools")
