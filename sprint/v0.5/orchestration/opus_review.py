"""orchestration/opus_review.py — submit a phase or final-review payload to Opus.

Reads phase evidence + relevant logs + rubric + reviewer system prompt; calls
the Anthropic API; parses the JSON verdict; writes review-N.json; updates
state.json. Used by review_with_opus.sh and final_review.sh.

Exit codes:
    0 — APPROVE
    1 — REVISE
    2 — ABORT
    78 — API or input error (no verdict produced)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("error: anthropic package not installed. pip install anthropic", file=sys.stderr)
    sys.exit(78)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from state_helpers import read_state, add_cost  # noqa: E402


REVIEW_MODEL = os.environ.get("RASPUTIN_OMNITOOL_REVIEWER_MODEL", "claude-opus-4-7")

# Pricing — keep aligned with agent/observability.py
PRICE_PER_M = {
    "claude-opus-4-7": (15.0, 75.0),
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-haiku-4-5": (0.80, 4.0),
}


def estimate_cost(tokens_in: int, tokens_out: int, model: str = REVIEW_MODEL) -> float:
    in_p, out_p = PRICE_PER_M.get(model, (15.0, 75.0))
    return (tokens_in / 1_000_000) * in_p + (tokens_out / 1_000_000) * out_p


def collect_logs(phase: int) -> dict[str, str]:
    """Best-effort gather of log files written by Sisyphus during the phase."""
    root = Path("sprint/v0.5")
    candidates = {
        "pytest": f"phase-{phase}-pytest.log",
        "ruff": f"phase-{phase}-ruff.log",
        "real_planner": f"phase-{phase}-real-planner.log",
        "real_executor": f"phase-{phase}-real.log",
        "live_demo": f"phase-{phase}-live-demo.log",
        "metadata": f"phase-{phase}-metadata.json",
        "postmerge_pytest": f"phase-{phase}-postmerge-pytest.log",
    }
    out: dict[str, str] = {}
    for key, fname in candidates.items():
        p = root / fname
        if p.exists():
            text = p.read_text(encoding="utf-8", errors="replace")
            # truncate huge logs
            if len(text) > 40_000:
                text = text[:20_000] + "\n... [log truncated] ...\n" + text[-20_000:]
            out[key] = text
    return out


def collect_diff_stat(phase: int) -> str:
    import subprocess
    state = read_state()
    branch = state.get("branches", {}).get(str(phase), f"sprint/v0.5-phase{phase}")
    prev_phase = phase - 1
    prev_branch = state.get("branches", {}).get(str(prev_phase), f"sprint/v0.5-phase{prev_phase}")
    base_ref = prev_branch if prev_phase >= 0 else "sprint/v0.5"
    try:
        r = subprocess.run(
            ["git", "diff", "--stat", f"{base_ref}..{branch}"],
            capture_output=True, text=True, timeout=10,
        )
        return r.stdout
    except Exception as e:
        return f"(diff stat unavailable: {e})"


def collect_prior_reviews() -> list[dict]:
    out: list[dict] = []
    for p in sorted(Path("sprint/v0.5").glob("review-*.json")):
        try:
            out.append(json.loads(p.read_text()))
        except Exception:
            continue
    return out


def build_payload(scope: str, phase: int) -> dict:
    sprint_dir = Path("sprint/v0.5")
    if scope == "phase":
        rubric = Path("sprint/v0.5/rubrics/per-phase-rubric.md").read_text()
        evidence = (sprint_dir / f"phase-{phase}-evidence.md").read_text()
        phase_brief = next(Path("sprint/v0.5/phases").glob(f"PHASE-{phase}-*.md")).read_text()
    elif scope == "final":
        rubric = Path("sprint/v0.5/rubrics/final-rubric.md").read_text()
        evidence = (sprint_dir / "final-evidence.md").read_text()
        phase_brief = ""
    else:
        raise ValueError(f"unknown scope: {scope}")

    return {
        "scope": scope,
        "phase": phase,
        "rubric": rubric,
        "phase_brief": phase_brief,
        "evidence": evidence,
        "state": read_state(),
        "prior_reviews": collect_prior_reviews(),
        "diff_stat": collect_diff_stat(phase),
        "key_logs": collect_logs(phase),
    }


def call_opus(system_prompt: str, payload: dict) -> tuple[dict, int, int]:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    user_content = (
        "Review the following sprint material. Return ONLY valid JSON per the schema "
        "in the system prompt — no markdown fences, no preamble.\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    )

    last_exc: Exception | None = None
    for attempt, delay in enumerate([1, 4, 16]):
        try:
            response = client.messages.create(
                model=REVIEW_MODEL,
                max_tokens=2000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
            )
            break
        except Exception as exc:
            last_exc = exc
            if attempt < 2:
                time.sleep(delay)
                continue
            raise
    else:
        raise RuntimeError(f"anthropic call failed: {last_exc}")

    text_parts: list[str] = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            text_parts.append(block.text)
    raw = "\n".join(text_parts).strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()

    try:
        verdict = json.loads(raw)
    except json.JSONDecodeError as e:
        # save raw response for debugging
        Path("sprint/v0.5/review-raw.txt").write_text(raw)
        raise RuntimeError(f"Opus returned invalid JSON: {e}") from e

    tokens_in = response.usage.input_tokens
    tokens_out = response.usage.output_tokens
    return verdict, tokens_in, tokens_out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", required=True, choices=("phase", "final"))
    ap.add_argument("--phase", type=int, required=True)
    args = ap.parse_args()

    if "ANTHROPIC_API_KEY" not in os.environ:
        print("ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 78

    sys_prompt_path = Path("sprint/v0.5/prompts/reviewer-system.md")
    if not sys_prompt_path.exists():
        print(f"missing {sys_prompt_path}", file=sys.stderr)
        return 78
    sys_prompt = sys_prompt_path.read_text()

    try:
        payload = build_payload(args.scope, args.phase)
    except FileNotFoundError as e:
        print(f"input missing: {e}", file=sys.stderr)
        return 78

    try:
        verdict, tin, tout = call_opus(sys_prompt, payload)
    except Exception as exc:
        print(f"opus call failed: {exc}", file=sys.stderr)
        return 78

    cost = estimate_cost(tin, tout)
    verdict["_cost_usd"] = round(cost, 4)
    verdict["_tokens_in"] = tin
    verdict["_tokens_out"] = tout
    verdict["_model"] = REVIEW_MODEL
    verdict["_scope"] = args.scope
    verdict["_phase"] = args.phase

    review_path = Path(f"sprint/v0.5/review-{args.phase}.json")
    if args.scope == "final":
        review_path = Path("sprint/v0.5/review-final.json")
    review_path.write_text(json.dumps(verdict, indent=2, ensure_ascii=False))

    add_cost(cost)

    v = verdict.get("verdict", "ABORT")
    print(f"VERDICT: {v}  (cost ${cost:.4f}, tokens {tin}/{tout})")
    if v == "APPROVE":
        return 0
    if v == "REVISE":
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
