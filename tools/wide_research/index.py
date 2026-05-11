"""tools/wide_research/index.py — Parallel multi-source research via sub-goal orchestration.

Breaks a research topic into sub-queries, executes them in parallel using
available tools, and aggregates results into a coherent report.
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from openai import OpenAI


def run(inputs: dict[str, Any]) -> dict[str, Any]:
    topic = inputs.get("topic", "")
    if not topic:
        return {"error": {"code": "INVALID_INPUT", "message": "Missing 'topic' parameter"}}

    max_sub_queries = int(inputs.get("max_sub_queries", 5))
    depth = inputs.get("depth", "standard")  # "shallow" | "standard" | "deep"

    # Step 1: Use LLM to decompose topic into sub-queries
    sub_queries = _decompose(topic, max_sub_queries, depth)
    if "error" in sub_queries:
        return sub_queries

    # Step 2: Execute each sub-query via web_search (or catalog lookup)
    results = []
    for sq in sub_queries:
        result = _execute_sub_query(sq)
        results.append({"query": sq, "result": result})

    # Step 3: Synthesize results into a report
    report = _synthesize(topic, results)

    # Write report to disk
    outputs_dir = Path(os.environ.get("RASPUTIN_OMNITOOL_OUTPUTS_DIR", "outputs"))
    outputs_dir.mkdir(parents=True, exist_ok=True)
    report_path = outputs_dir / f"research-{uuid.uuid4().hex[:8]}.md"
    report_path.write_text(report, encoding="utf-8")

    return {
        "result": {
            "topic": topic,
            "sub_queries": sub_queries,
            "report": report,
            "path": str(report_path),
        }
    }


def _decompose(topic: str, max_sub_queries: int, depth: str) -> list[str]:
    """Use LLM to break topic into focused sub-queries."""
    client = OpenAI(
        base_url=os.environ.get("RASPUTIN_OMNITOOL_EXECUTOR_ENDPOINT", "http://localhost:11434/v1"),
        api_key=os.environ.get("OPENCODE_ZEN_API_KEY"),
    )

    depth_instruction = {
        "shallow": "Return 2-3 broad overview queries.",
        "standard": "Return 4-6 focused queries covering different angles.",
        "deep": "Return 6-8 very specific queries for exhaustive coverage.",
    }.get(depth, depth_instruction["standard"])

    prompt = (
        f"Decompose this research topic into {max_sub_queries} focused search queries.\n"
        f"{depth_instruction}\n"
        f"Topic: {topic}\n"
        f"Return ONLY a JSON array of strings, e.g. [\"query 1\", \"query 2\"]."
    )

    try:
        resp = client.chat.completions.create(
            model=os.environ.get("RASPUTIN_OMNITOOL_PLANNER_MODEL", "gpt-oss-120b"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
        )
        content = resp.choices[0].message.content.strip()
        queries = json.loads(content)
        if not isinstance(queries, list):
            return {"error": {"code": "DECOMPOSITION_FAILED", "message": "LLM did not return a list"}}
        return queries[:max_sub_queries]
    except Exception as e:
        # Fallback: return topic as single query
        return [topic]


def _execute_sub_query(query: str) -> dict[str, Any]:
    """Execute a sub-query via web_search tool."""
    try:
        from tools.web_search.index import run as web_search_run
        result = web_search_run({"query": query, "max_results": 5})
        return result
    except Exception as e:
        return {"error": {"code": "SUB_QUERY_FAILED", "message": str(e)}}


def _synthesize(topic: str, results: list[dict]) -> str:
    """Use LLM to synthesize sub-query results into a report."""
    client = OpenAI(
        base_url=os.environ.get("RASPUTIN_OMNITOOL_EXECUTOR_ENDPOINT", "http://localhost:11434/v1"),
        api_key=os.environ.get("OPENCODE_ZEN_API_KEY"),
    )

    # Build context from results
    context_parts = []
    for r in results:
        query = r.get("query", "")
        res = r.get("result", {})
        if "error" in res:
            context_parts.append(f"Query: {query}\nError: {res['error']}\n")
        elif "result" in res:
            items = res["result"].get("results", [])
            context_parts.append(f"Query: {query}\n")
            for item in items[:3]:
                context_parts.append(f"  - {item.get('title', '')}: {item.get('snippet', '')} ({item.get('url', '')})\n")
            context_parts.append("\n")

    context = "".join(context_parts)

    prompt = (
        f"Synthesize these research findings into a comprehensive markdown report on: {topic}\n\n"
        f"Findings:\n{context}\n\n"
        f"Write a well-structured report with sections, key findings, and sources."
    )

    try:
        resp = client.chat.completions.create(
            model=os.environ.get("RASPUTIN_OMNITOOL_PLANNER_MODEL", "gpt-oss-120b"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return f"# Research: {topic}\n\n## Raw Findings\n{context}"


if __name__ == "__main__":
    payload = json.loads(__import__("sys").stdin.read())
    print(json.dumps(run(payload)))
