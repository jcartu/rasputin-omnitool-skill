"""Open WebUI Tool: invoke rasputin-omnitool-skill from chat.

Place this file in Open WebUI's Tools section.

When the user sends a message, this tool:
1. Sends the message text to agent.run_goal as the goal.
2. Streams executor step updates back as in-chat status messages.
3. Returns the final result (verdict + summary + artifact links) as the response.

Configuration via Valves:
- max_cost_usd: per-goal cost ceiling (default 0.50)
- show_steps: stream executor steps to chat (default True)
- outputs_base_url: where outputs/ is mounted; used to make artifact links
- rasputin_repo_path: path to the skill repo on disk (for sys.path)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field


class Tools:
    """Open WebUI Tool entry point. The class is auto-discovered."""

    class Valves(BaseModel):
        """User-configurable settings shown in Open WebUI."""

        max_cost_usd: float = Field(default=0.50, description="Per-goal cost ceiling in USD")
        show_steps: bool = Field(default=True, description="Stream executor steps to chat")
        outputs_base_url: str = Field(
            default="file:///app/backend/data/outputs",
            description="Where outputs/ is mounted; used to make artifact links",
        )
        rasputin_repo_path: str = Field(
            default="/home/josh/workspace/rasputin-omnitool-skill",
            description="Path to the skill repo on disk (for sys.path)",
        )

    def __init__(self):
        self.valves = self.Valves()
        self.citation = True

    async def run_goal(
        self,
        goal: str,
        __event_emitter__: Optional[Any] = None,
        __user__: Optional[dict] = None,
    ) -> str:
        """Run a rasputin-omnitool goal and return the result.

        Open WebUI calls this when the user invokes the tool. The goal
        is the user's chat message.
        """
        # Make the skill importable
        repo = self.valves.rasputin_repo_path
        if repo not in sys.path:
            sys.path.insert(0, repo)

        # Set cost ceiling per this invocation
        os.environ["RASPUTIN_OMNITOOL_MAX_COST_USD"] = str(self.valves.max_cost_usd)

        try:
            from agent import run_goal as _run_goal
        except ImportError as exc:
            return f"❌ Could not load rasputin-omnitool-skill: {exc}\n\nCheck the rasputin_repo_path valve."

        if self.valves.show_steps and __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": "Planning...", "done": False},
                }
            )

        try:
            result = _run_goal(goal)
        except Exception as exc:
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": f"Error: {exc}", "done": True},
                    }
                )
            return f"❌ Goal failed: {type(exc).__name__}: {exc}"

        # Stream final status
        if __event_emitter__:
            await __event_emitter__(
                {"type": "status", "data": {"description": "Done", "done": True}}
            )

        return self._format_response(result)

    def _format_response(self, result: dict) -> str:
        """Turn run_goal's dict result into a nice chat reply."""
        if result.get("halted"):
            reason = result.get("reason", "unknown")
            details = result.get("details", {})
            return (
                f"⛔ **Goal halted:** {reason}\n\n"
                f"Details: `{json.dumps(details, indent=2)}`\n\n"
                f"To continue, raise `RASPUTIN_OMNITOOL_MAX_COST_USD` "
                f"(currently ${self.valves.max_cost_usd:.2f}) or simplify the goal."
            )

        review = result.get("review")
        verdict = getattr(review, "verdict", str(review))
        notes = getattr(review, "notes", "")
        artifacts = self._collect_artifacts(result)

        out = f"### Verdict: **{verdict}**\n\n"
        if notes:
            out += f"{notes}\n\n"

        if artifacts:
            out += "**Artifacts:**\n"
            for a in artifacts:
                rel = self._artifact_link(a)
                out += f"- [{Path(a).name}]({rel})\n"
            out += "\n"

        return out

    def _collect_artifacts(self, result: dict) -> list[str]:
        """Walk the result for artifact paths."""
        paths: list[str] = []
        for r in result.get("results", []):
            if isinstance(r, dict):
                rdata = r.get("result", {})
                for key in (
                    "artifact_path",
                    "audio_path",
                    "image_path",
                    "source_path",
                    "preview_url",
                    "report_path",
                    "path",
                ):
                    if key in rdata and isinstance(rdata[key], str):
                        paths.append(rdata[key])
        return paths

    def _artifact_link(self, path: str) -> str:
        """Convert an absolute path to a clickable link."""
        if path.startswith(("http://", "https://", "file://")):
            return path
        # Local path: convert to configured base URL
        return f"{self.valves.outputs_base_url}/{Path(path).name}"
