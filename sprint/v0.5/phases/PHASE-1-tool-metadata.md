# PHASE 1 — Tool metadata: fix the planner catalog

**Branch:** `sprint/v0.5-phase1`
**Estimated effort:** 3–4 hours
**Depends on:** Phase 0 approved

## Objective

Make `load_tool_metadata()` return a real catalog the planner can use, and prove it works end-to-end with at least one real tool call. After this phase, the v0.4 critical bug is gone and the existing static executor works for the first time.

## The bug

`agent/tool_registry.py:167-171` ships an empty list comprehension:

```python
def load_tool_metadata() -> list[dict]:
    """Load tool metadata for the planner (name + description)."""
    tools = discover_tools()
    return [
    ]
```

Result: planner sees no tools, every plan that names a tool fails validation, every goal dies.

## Concrete changes

### 1. Implement `load_tool_metadata()`

Use the skeleton in `skeletons/tool_metadata.py`. Replace the placeholder in `agent/tool_registry.py` with a real implementation that returns, per tool:

```python
{
    "name": str,                        # canonical name = directory name
    "version": str,                     # from manifest
    "description": str,                 # from manifest
    "inputs": dict,                     # the inputs JSON schema slice
    "outputs": dict,                    # the outputs schema slice
    "errors": list[str],                # error codes the tool can return
    "tags": list[str],                  # from manifest, optional
    "available": bool,                  # True iff the tool's backends probed OK
    "backend_statuses": list[dict],     # each {name, available, message}
}
```

Only `available: True` tools should be returned by default. Add a kwarg `include_unavailable: bool = False` for completeness (used by tests).

Tool metadata MUST be live — re-probe backends if older than 30 seconds. Add a TTL cache.

### 2. Hard contract: capability tags

Every tool's manifest must declare a `tags` field with at least one entry. This is the planner's main hint. Add tags to every existing manifest:

| Tool | Tags |
|---|---|
| browser | `["web", "automation", "interactive"]` |
| catalog | `["meta", "discovery"]` |
| coding_agent | `["code", "editing", "files"]` |
| crawl4ai | `["web", "fetch", "markdown"]` |
| deliverables | `["output", "file", "report"]` |
| docling | `["document", "parse", "files"]` |
| image_gen | `["media", "image", "generation"]` |
| mail | `["communication", "email"]` |
| memory | `["state", "memory", "retrieval"]` |
| music_gen | `["media", "audio", "generation"]` |
| sandbox | `["compute", "code", "execution"]` |
| slides | `["output", "presentation"]` |
| stt | `["media", "audio", "transcription"]` |
| tts | `["media", "audio", "synthesis"]` |
| video_gen | `["media", "video", "generation"]` |
| web_search | `["web", "search"]` |

Update `agent/schemas/tool_manifest.schema.json` to require `tags` (minItems: 1).

### 3. Planner prompt must consume the metadata

`prompts/planner.md` currently has examples with tiny stub catalogs. Update the prompt so the planner is told to:
- Pick tools by tag match first, name match second.
- NEVER use a tool whose `available: false`.
- Justify each tool choice in the task `goal` field with the tag(s) that matched.

Add a section "Tool catalog format" describing the metadata shape.

### 4. One real end-to-end test

Create `tests/test_real_e2e_phase1.py` that:
- Sets `RASPUTIN_OMNITOOL_MOCK_TOOLS=true` for tool execution (mock backends).
- Calls `load_tool_metadata()` for real.
- Calls a real planner (with `OPENCODE_ZEN_API_KEY` or skip if not set).
- Verifies the planner returns at least one task with a non-null tool name.
- Verifies that name is in the metadata.

Mark it `@pytest.mark.real_planner` so it's runnable but skippable without the API key.

### 5. Update existing tests

The `test_loop_integration.py::test_run_goal_with_mocked_tools` test currently monkey-patches `agent.load_tool_metadata` with a stubbed list. Change it to call the real function (with mocked backends) and assert the real metadata flows through.

The `test_tool_registry.py` test should add coverage for:
- `load_tool_metadata()` returns non-empty when tools exist.
- TTL cache works (two calls within 30s return the same object, third call after sleeping > 30s re-probes).
- `include_unavailable=True` returns broken tools too.

## Files to change

```
M  agent/tool_registry.py            # implement load_tool_metadata + TTL cache
M  agent/schemas/tool_manifest.schema.json  # require tags
M  prompts/planner.md                # describe metadata, scoring
M  tools/*/manifest.json             # add tags array (every tool)
M  tests/test_tool_registry.py
M  tests/test_loop_integration.py
A  tests/test_real_e2e_phase1.py     # new
```

## Acceptance criteria

- `python -c "from agent.tool_registry import load_tool_metadata; m = load_tool_metadata(); print(len(m))"` returns a non-zero integer matching the count of available tools.
- Every tool manifest passes the updated schema (requires `tags`).
- `pytest -v tests/test_tool_registry.py` passes including the new TTL test.
- `pytest -v tests/test_loop_integration.py::test_run_goal_with_mocked_tools` passes against real `load_tool_metadata`.
- `pytest -v -m real_planner tests/test_real_e2e_phase1.py` passes when `OPENCODE_ZEN_API_KEY` is set.
- The planner, given the real metadata, produces a valid plan for the canary goal "Crawl example.com and produce a 1-paragraph markdown summary saved to outputs/."

## Self-verification

```bash
pytest -v tests/test_tool_registry.py tests/test_loop_integration.py 2>&1 | tee sprint/v0.5/phase-1-pytest.log

# Smoke the real planner if key present:
if [ -n "$OPENCODE_ZEN_API_KEY" ]; then
  pytest -v -m real_planner tests/test_real_e2e_phase1.py 2>&1 | tee sprint/v0.5/phase-1-real-planner.log
fi

# Sanity-print the metadata:
python -c "
import json
from agent.tool_registry import load_tool_metadata
m = load_tool_metadata(include_unavailable=True)
print(json.dumps([{'name': t['name'], 'tags': t['tags'], 'available': t['available']} for t in m], indent=2))
" | tee sprint/v0.5/phase-1-metadata.json
```

## Phase evidence

Per `rubrics/per-phase-rubric.md`. Must include:

- The bug was at line N of `agent/tool_registry.py` and the fix is line-N-to-M with the new function body inlined in the evidence file.
- `phase-1-metadata.json` (the live tool catalog).
- Counts: tools discovered, tools available, tools unavailable, tools with tags.
- The exact plan emitted by the real planner for the canary goal (paste JSON).

## Halt conditions

- If real planner consistently emits plans referencing tools not in the metadata, stop. Either the prompt is wrong or the model is too weak. Document and ask Joshua before forcing through.
- If TTL cache logic interacts badly with backend probing (test flakiness), pin TTL to test-injectable rather than removing the cache. Caching is mandatory; we cannot probe every planner call.

## Out of scope

- Replacing the executor (Phase 2).
- Any change to tool implementations (Phase 0 is the cleanup; new tools come later).
- Re-architecting backend probing — the existing `probe_backends()` is fine; just wire it through.
