"""Opus-backed reviewer for rasputin-omnitool-skill execution traces."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

try:
    import anthropic
except ModuleNotFoundError:
    anthropic = SimpleNamespace(Anthropic=None)

from agent.config import CONFIG
from agent.executor import ExecutionTrace
from agent.observability import observe, check_cost_ceiling, record_call_cost, extract_usage

Verdict = Literal["APPROVE", "REVISE", "ABORT"]

_MAX_TRACE_CHARS = 200_000
_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "reviewer.md"


class ReviewParseError(ValueError):
    """Raised when the reviewer model returns an invalid review payload."""


@dataclass(frozen=True)
class Review:
    """Structured review result for a completed or checkpointed execution."""

    verdict: Verdict
    notes: str
    findings: list[str] = field(default_factory=list)


@observe("reviewer.review")
def review(trace: ExecutionTrace, artifacts: list[str]) -> Review:
    """Review an execution trace and artifacts with Claude Opus."""

    # Check cost ceiling before LLM call
    check_cost_ceiling(CONFIG.reviewer_model, est_prompt=20_000, est_completion=2_000)

    system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model=CONFIG.reviewer_model,
        max_tokens=1200,
        temperature=0,
        system=system_prompt,
        messages=[{"role": "user", "content": _build_user_message(trace, artifacts)}],
    )
    # Record cost telemetry
    prompt_tokens, completion_tokens = extract_usage(response)
    record_call_cost(CONFIG.reviewer_model, prompt_tokens, completion_tokens)

    return _parse_review(_response_text(response))


def _build_user_message(trace: ExecutionTrace, artifacts: list[str]) -> str:
    payload = {
        "trace": _dataclass_to_dict(trace),
        "artifacts_for_review": artifacts,
    }
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    if len(serialized) > _MAX_TRACE_CHARS:
        serialized = serialized[:_MAX_TRACE_CHARS] + "\n... [trace truncated to approximately 50k tokens]"
    return "Review this execution trace and return only the required JSON.\n\n" + serialized


def _dataclass_to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    return value


def _response_text(response: Any) -> str:
    parts: list[str] = []
    for block in getattr(response, "content", []) or []:
        text = getattr(block, "text", None)
        if text is None and isinstance(block, dict):
            text = block.get("text")
        if text:
            parts.append(str(text))
    return "\n".join(parts).strip()


def _parse_review(raw_text: str) -> Review:
    if not raw_text:
        raise ReviewParseError("Reviewer response was empty.")

    try:
        payload = json.loads(_extract_json(raw_text))
    except json.JSONDecodeError as exc:
        raise ReviewParseError(f"Reviewer response was not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ReviewParseError("Reviewer response JSON must be an object.")

    verdict = payload.get("verdict")
    notes = payload.get("notes")
    findings = payload.get("findings", [])

    if verdict not in {"APPROVE", "REVISE", "ABORT"}:
        raise ReviewParseError("Reviewer verdict must be APPROVE, REVISE, or ABORT.")
    if not isinstance(notes, str):
        raise ReviewParseError("Reviewer notes must be a string.")
    if not isinstance(findings, list) or not all(isinstance(item, str) for item in findings):
        raise ReviewParseError("Reviewer findings must be a list of strings.")

    return Review(verdict=verdict, notes=notes, findings=findings)


def _extract_json(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text
