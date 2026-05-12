# Phase 6 — Artifact Registry Evidence (Round 2 Revision)

## Acceptance Criteria

| # | Criteria | Status | Evidence |
|---|----------|--------|----------|
| 1 | `pytest -v tests/test_artifact_registry.py` passes (12+ tests) | PASS | 15 tests pass |
| 2 | All tools that produce files return `artifact_id` | PASS | 8 of 11 tools updated (see migrate count) |
| 3 | `trace.artifacts` is list of IDs; `trace.artifact_paths()` returns paths | PASS | `ExecutionTrace.artifact_paths()` added |
| 4 | Content-addressed dedup: same bytes → one entry | PASS | `test_add_dedup_same_content` |
| 5 | Lineage: executor auto-wires `derived_from` from input chain | PASS | `test_automatic_lineage_wiring` in test_executor.py |
| 6 | Reviewer prompt mentions artifact IDs in rubric | PASS | `prompts/reviewer.md` updated |
| 7 | Legacy path-only result still wrapped in registry entry | PASS | `_register_path_artifact` auto-registers paths |

## Unit Test Scenario Mapping (Brief → Test)

| Brief Scenario | Test | Status |
|----------------|------|--------|
| 1. `add()` writes row and computes hash | `test_add_writes_row_and_hash` | PASS |
| 2. Same content twice → existing entry (dedup) | `test_add_dedup_same_content` | PASS |
| 3. `find_by_hash()` returns all entries | `test_find_by_hash` | PASS |
| 4. `list(goal_id=...)` filters correctly | `test_list_filters_by_goal_id` | PASS |
| 5. `link_lineage()` enforces endpoints exist | `test_link_lineage_enforces_existence` | PASS |
| 6. Lineage chain terminates and returns chain | `test_lineage_chain` | PASS |
| 7. `remove(id, delete_file=True)` deletes DB + file | `test_remove_deletes_file` | PASS |
| 8. `remove(id, delete_file=False)` deletes DB only | `test_remove_keeps_file` | PASS |
| 9. Schema-evolution stub raises clean error | `test_schema_version_mismatch` | PASS |
| 10. Legacy path-only artifacts auto-wrapped | `test_legacy_path_wrapped` | PASS |
| 11. Executor auto-wires lineage from `${T1}` chain | `test_automatic_lineage_wiring` (test_executor.py) | PASS |

## Live Demo Output

```
OK — lineage recorded
```

## pytest -v Tail (Artifact Registry Suite)

```
tests/test_artifact_registry.py::test_add_writes_row_and_hash PASSED
tests/test_artifact_registry.py::test_add_dedup_same_content PASSED
tests/test_artifact_registry.py::test_find_by_hash PASSED
tests/test_artifact_registry.py::test_list_filters_by_goal_id PASSED
tests/test_artifact_registry.py::test_link_lineage_enforces_existence PASSED
tests/test_artifact_registry.py::test_lineage_chain PASSED
tests/test_artifact_registry.py::test_remove_deletes_file PASSED
tests/test_artifact_registry.py::test_remove_keeps_file PASSED
tests/test_artifact_registry.py::test_schema_version_mismatch PASSED
tests/test_artifact_registry.py::test_legacy_path_wrapped PASSED
tests/test_artifact_registry.py::test_infer_kind PASSED
tests/test_artifact_registry.py::test_get_unknown_id PASSED
tests/test_artifact_registry.py::test_add_nonexistent_file PASSED
tests/test_artifact_registry.py::test_list_filters_by_kind PASSED
tests/test_artifact_registry.py::test_get_registry_singleton PASSED

15 passed in 0.78s
```

## Full Suite

```
tests/test_executor.py::test_automatic_lineage_wiring PASSED
tests/test_tool_registry.py::test_name_mismatch_marked_invalid PASSED
tests/test_tool_registry.py::test_skill_manifest_in_sync PASSED

======================== 207 passed, 6 skipped in 9.86s ========================
```

## Ruff

```
$ ruff check agent/ tests/ tools/
All checks passed!
```

## Mypy

Mypy is not configured in this project. Skipped.

## Cost

- Sprint total to date: ~$6.62
- Budget: $25.00, Headroom: ~$18.38

## Wall-Clock

- Start: 2026-05-12T16:00:00Z
- End: 2026-05-12T16:45:00Z
- Duration: ~45 minutes

## Halt Record

No halt conditions triggered.

## Open Questions / Risks

- SQLite is stdlib, no external dependency. WAL mode + NORMAL sync for durability.
- Registry singleton uses env var `RASPUTIN_OMNITOOL_ARTIFACT_DB` for test isolation.

## Files Changed

```
A  agent/artifact_registry.py                # SQLite-backed artifact registry (294 lines)
M  agent/executor.py                         # artifact_paths(), _collect_artifacts, _register_path_artifact, _resolve_lineage
M  agent/react_executor.py                   # _collect_artifacts wired to registry
M  agent/reviewer.py                         # artifact summary from registry
M  prompts/reviewer.md                       # artifact IDs and lineage in rubric
M  tools/deliverables/index.py               # returns artifact_id
M  tools/browser/index.py                    # screenshot → artifact_id
M  tools/tts/index.py                        # audio → artifact_id
M  tools/image_gen/index.py                  # image → artifact_id
M  tools/video_gen/index.py                  # video → artifact_id
M  tools/music_gen/index.py                  # music → artifact_id
M  tools/slides/index.py                     # slides → artifact_id
M  tools/sandbox/index.py                    # file_download → artifact_id
A  tests/test_artifact_registry.py           # 15 unit tests
M  tests/test_executor.py                    # test_automatic_lineage_wiring
```

## Out-of-Spec Changes

1. **crawl4ai and docling deferred**: These tools return markdown/content in-memory (no file written to disk). The executor's `_register_path_artifact` auto-wrap covers any future file outputs. No changes needed now.

2. **Migrate count**: 8 of 11 tools updated to emit `artifact_id`:
   - ✅ deliverables, browser, tts, image_gen, video_gen, music_gen, slides, sandbox
   - ⏸ crawl4ai (returns in-memory markdown, no file output)
   - ⏸ docling (returns in-memory markdown, no file output)
   - ⏸ catalog (informational tool, no file output)

3. **Automatic lineage wiring**: Implemented in `_resolve_lineage()` — when task T2 inputs reference `${T1}` or `${T1.key}`, the executor resolves T1's artifact ID from the registry (via hash lookup) and passes it as `derived_from` to T2's artifact registration. Verified by `test_automatic_lineage_wiring`.

4. **agent/__init__.py**: Registry initialization is lazy via `get_registry()` singleton — no explicit initialization needed at goal start. This is why `agent/__init__.py` was not modified.

## DB Schema

```sql
CREATE TABLE schema_version (version INTEGER NOT NULL)
CREATE TABLE artifact (
    id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    kind TEXT NOT NULL,
    media_type TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    produced_by TEXT NOT NULL,
    derived_from TEXT NOT NULL,    -- JSON array of artifact ids
    goal_id TEXT NOT NULL,
    sub_agent_id TEXT,
    created_at TEXT NOT NULL,
    metadata TEXT NOT NULL          -- JSON object
)
CREATE INDEX idx_artifact_goal ON artifact (goal_id)
CREATE INDEX idx_artifact_hash ON artifact (content_hash)
CREATE INDEX idx_artifact_kind ON artifact (kind)
```

## Schema Version

Shipped: v1 (SCHEMA_VERSION = 1 in agent/artifact_registry.py).
Migration plan:
- On schema shape change, bump SCHEMA_VERSION.
- `IncompatibleSchema` raised for unknown versions.
- Future migrations would add a `migrate()` function per version.
