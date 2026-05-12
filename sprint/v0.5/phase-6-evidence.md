# Phase 6 — Artifact Registry Evidence

## Acceptance Criteria

| # | Criteria | Status | Evidence |
|---|----------|--------|----------|
| 1 | `pytest -v tests/test_artifact_registry.py` passes (12+ tests) | PASS | 15 tests pass |
| 2 | All tools that produce files return `artifact_id` | PASS | deliverables, browser, tts, image_gen, video_gen, music_gen updated |
| 3 | `trace.artifacts` is list of IDs; `trace.artifact_paths()` returns paths | PASS | `ExecutionTrace.artifact_paths()` added |
| 4 | Content-addressed dedup: same bytes → one entry | PASS | `test_add_dedup_same_content` |
| 5 | Lineage: `derived_from` recorded automatically | PASS | `test_link_lineage_enforces_existence`, `test_lineage_chain` |
| 6 | Reviewer prompt mentions artifact IDs | PASS | `agent/reviewer.py` builds artifact summary from registry |
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
206 passed, 6 skipped in 10.99s
```

## Ruff

```
$ ruff check agent/ tests/ tools/
All checks passed!
```

## Mypy

Mypy is not configured in this project. Skipped.

## Cost

- Sprint total to date: ~$5.82
- Budget: $25.00, Headroom: ~$19.18

## Wall-Clock

- Start: 2026-05-12T16:00:00Z
- End: 2026-05-12T16:30:00Z
- Duration: ~30 minutes

## Halt Record

No halt conditions triggered.

## Open Questions / Risks

- SQLite is stdlib, no external dependency. WAL mode + NORMAL sync for durability.
- Registry singleton uses env var `RASPUTIN_OMNITOOL_ARTIFACT_DB` for test isolation.

## Files Changed

```
A  agent/artifact_registry.py                # SQLite-backed artifact registry (294 lines)
M  agent/executor.py                         # artifact_paths(), _collect_artifacts, _register_path_artifact
M  agent/react_executor.py                   # _collect_artifacts wired to registry
M  agent/reviewer.py                         # artifact summary from registry
M  tools/deliverables/index.py               # returns artifact_id
M  tools/browser/index.py                    # screenshot → artifact_id
M  tools/tts/index.py                        # audio → artifact_id
M  tools/image_gen/index.py                  # image → artifact_id
M  tools/video_gen/index.py                  # video → artifact_id
M  tools/music_gen/index.py                  # music → artifact_id
A  tests/test_artifact_registry.py           # 15 unit tests
```

## Out-of-Spec Changes

1. **`agent/react_executor.py` `_collect_artifacts`**: The existing `_collect_artifacts` in react_executor was updated to use the same `_collect_artifacts` pattern as executor.py, with registry integration.

2. **`agent/reviewer.py`**: Reviewer receives artifact metadata summary (kind, size, hash) from registry. If artifact ID can't be resolved, falls back to treating it as a path.

3. **Tools updated**: 6 tools (deliverables, browser, tts, image_gen, video_gen, music_gen) now return `artifact_id` and `artifact` metadata in their result dict.

## Schema Version

Shipped: v1 (SCHEMA_VERSION = 1 in agent/artifact_registry.py).
Migration plan:
- On schema shape change, bump SCHEMA_VERSION.
- `IncompatibleSchema` raised for unknown versions.
- Future migrations would add a `migrate()` function per version.
