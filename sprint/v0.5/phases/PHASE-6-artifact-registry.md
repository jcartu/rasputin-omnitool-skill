# PHASE 6 — Artifact registry (typed files)

**Branch:** `sprint/v0.5-phase6`
**Estimated effort:** 3–4 hours
**Depends on:** Phase 5 approved

## Objective

Replace `ExecutionTrace.artifacts: list[str]` with a typed registry. Each artifact has an ID, content hash, kind, producer, and lineage. Reviewer and downstream tools reference artifacts by ID, not by string paths.

## Why

Today artifacts are just paths. The reviewer can't tell which step produced what, the executor can't dedupe identical outputs, and the user can't trace lineage when something looks wrong. Adding this now (before sub-agents in Phase 7) is necessary — sub-agents will produce many artifacts and we need to compose them.

## Architecture

### Artifact model

```python
@dataclass(frozen=True)
class Artifact:
    id: str                        # ULID
    path: str                      # absolute
    kind: str                      # 'document'|'image'|'audio'|'video'|'code'|'data'|'log'
    media_type: str                # MIME, best-effort
    content_hash: str              # sha256 hex of the file bytes
    size_bytes: int
    produced_by: str               # tool name + step id, e.g. "deliverables/step-7"
    derived_from: list[str]        # IDs of artifacts that were inputs to producing this
    goal_id: str
    sub_agent_id: str | None       # if produced inside a sub-agent
    created_at: datetime
    metadata: dict                 # tool-specific (e.g. {"format": "pdf", "pages": 12})
```

### Registry

```python
class ArtifactRegistry:
    def __init__(self, db_path: Path): ...
    def add(self, path: Path, kind: str, produced_by: str, goal_id: str, ...) -> Artifact: ...
    def get(self, artifact_id: str) -> Artifact: ...
    def list(self, goal_id: str | None = None, kind: str | None = None) -> list[Artifact]: ...
    def find_by_hash(self, content_hash: str) -> list[Artifact]: ...
    def link_lineage(self, artifact_id: str, derived_from: list[str]) -> None: ...
    def remove(self, artifact_id: str, delete_file: bool = False) -> None: ...
```

Backing store: SQLite at `~/.rasputin/artifacts/registry.db`. One table, simple schema, no migrations needed for v0.5.

### Tool changes

Every tool that produces a file now does two things:
1. Writes the file (as today).
2. Calls `registry.add(...)` and returns the artifact ID in its result.

The standard result shape gets an `artifacts` field with ID references:

```python
# Old result:
{"result": {"path": "/abs/path/to/report.md"}}

# New result:
{
    "result": {
        "path": "/abs/path/to/report.md",       # kept for backwards compat
        "artifact_id": "01H...",
        "artifact": {
            "id": "01H...",
            "path": "/abs/path/to/report.md",
            "kind": "document",
            "media_type": "text/markdown",
            "size_bytes": 1234,
            "content_hash": "abc..."
        }
    }
}
```

`ExecutionTrace.artifacts` becomes `list[str]` of IDs (not paths). A helper `trace.artifact_paths()` returns the resolved paths.

### Executor changes

`agent/react_executor.py`:
- Detects `artifact` or `artifact_id` in tool results.
- Adds the ID to `trace.artifacts`.
- For deliverables tools that return `artifacts: [{path: ...}, ...]` (existing shape), wraps each in `registry.add()` retroactively.

### Reviewer changes

`agent/reviewer.py`:
- Reviewer receives a summary of artifacts (ID, kind, size, hash) rather than just paths.
- Reviewer can request a spot check on any artifact ID via a new tool-style escape hatch (NOT NEEDED for v0.5 — design it but don't implement). For v0.5, the reviewer prompt is updated to make use of the new metadata in its rubric.

### Backwards compatibility

Tools that don't yet emit artifact_ids (legacy tools) still work: the executor wraps their path outputs in `registry.add()` automatically, inferring kind from extension.

## Skeleton

See `skeletons/artifact_registry.py`. Includes the SQLite schema, `add()` with hashing, lineage helpers.

## Files to change

```
A  agent/artifact_registry.py
M  agent/__init__.py                     # initialize registry at goal start
M  agent/react_executor.py               # detect + register artifacts
M  agent/reviewer.py                     # consume artifact metadata
M  prompts/reviewer.md                   # mention artifact IDs and lineage
M  tools/deliverables/index.py           # return artifact_id
M  tools/image_gen/index.py              # return artifact_id
M  tools/video_gen/index.py              # return artifact_id
M  tools/music_gen/index.py              # return artifact_id
M  tools/tts/index.py                    # return artifact_id
M  tools/slides/index.py                 # return artifact_id
M  tools/sandbox/index.py                # file_download / file_upload → artifact_id
M  tools/crawl4ai/index.py               # if saving markdown to disk, register it
M  tools/docling/index.py                # output document → artifact
M  tools/browser/index.py                # screenshot → artifact_id
A  tests/test_artifact_registry.py
M  tests/test_*.py                       # update tool tests to assert artifact_id present
```

## Acceptance criteria

- `pytest -v tests/test_artifact_registry.py` passes (12+ tests).
- All tools that produce files return an `artifact_id` in their result.
- `trace.artifacts` is a list of IDs; `trace.artifact_paths()` returns paths.
- Content-addressed dedup: producing the same file bytes twice does NOT create two entries; `find_by_hash()` returns one.
- Lineage: a `deliverables` call that consumes a `crawl4ai` output records `derived_from=[crawl_artifact_id]` (the executor wires this automatically based on the tool input chain).
- Reviewer prompt mentions artifact IDs in its rubric.
- Legacy tool result shape (just `path`) is still wrapped in a registry entry — no breakage.

## Unit-test scenarios that MUST exist

1. `add()` writes a row and computes the correct hash.
2. `add()` of the same content twice returns the existing entry (dedup).
3. `find_by_hash()` returns all entries with that hash.
4. `list(goal_id=...)` filters correctly.
5. `link_lineage()` enforces both endpoints exist; missing IDs → error.
6. Resolving a lineage chain (`derived_from → derived_from → ...`) terminates and returns the chain.
7. `remove(id, delete_file=True)` deletes both DB row and file.
8. `remove(id, delete_file=False)` deletes DB row but not file.
9. Schema-evolution stub: opening a DB with a future schema version raises a clean error.
10. Migration from legacy path-only artifacts: a trace from Phase 5 (no IDs) is auto-wrapped on read.

## Self-verification

```bash
pytest -v tests/test_artifact_registry.py 2>&1 | tee sprint/v0.5/phase-6-pytest.log

# Live demo: produce two artifacts, check lineage.
python -c "
from pathlib import Path
from agent.artifact_registry import get_registry
reg = get_registry()
src = Path('/tmp/src.md')
src.write_text('# Source')
a = reg.add(src, kind='document', produced_by='crawl4ai/step-1', goal_id='g-demo')

dst = Path('/tmp/dst.pdf')
dst.write_bytes(b'%PDF-1.4 fake')
b = reg.add(dst, kind='document', produced_by='deliverables/step-2', goal_id='g-demo')
reg.link_lineage(b.id, [a.id])

assert reg.get(b.id).derived_from == [a.id]
print('OK — lineage recorded')
" 2>&1 | tee sprint/v0.5/phase-6-live-demo.log
```

## Phase evidence

- Migrate count: how many existing tools were updated to emit artifact_id.
- Dedup test output: confirmation that identical content is de-duplicated.
- Lineage demo output.
- DB schema (paste `.schema` from sqlite3).

## Halt conditions specific to Phase 6

- If the dedup approach breaks any existing test (e.g. a test expects two distinct artifact entries for the same content), fix the test, not the dedup. Same content = same artifact. If a test really needs two entries, it's writing different bytes; verify.
- If SQLite is heavy for some deployment target (it shouldn't be — it's stdlib), halt and propose a JSONL-based fallback. Don't sneakily make it dual-backend without review.

## Out of scope for Phase 6

- Artifact previews / thumbnails.
- Cloud storage backends.
- Cross-machine artifact sync.
- Permissions / ACLs on artifacts.
- Artifact "tags" beyond `kind` (planned for future).
