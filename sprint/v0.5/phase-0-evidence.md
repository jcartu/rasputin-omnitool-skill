# Phase 0 evidence — Truth pass (delete the lies)

## Summary
Removed all known-broken or fictitious surfaces from v0.4.0. Deleted `webapp_builder` and `wide_research` tool directories (2 tools, ~240 lines). Fixed `coding_agent` aider command (replaced non-existent `--repo` flag with positional file args). Fixed `mail` dead temp-file logic. Removed fictitious PyPI deps from `pyproject.toml` (`openclaw-skill-sdk`, `promptfoo`, `voxtral-tts`). Cleaned `docker-compose.yml` (removed fabricated GHCR images for Wan, MusicGen, and Langfuse stack). Fixed SearXNG port collision (8888→8889). Removed `/home/josh` default path from Open WebUI plugin. Updated manifest to 16 tools, README/SKILL.md counts aligned.

## Files touched
```
README.md                                     |  12 +--
SKILL.md                                      |   7 +-
agent/__init__.py                             |   6 +-
agent/executor.py                             |   3 +-
agent/observability.py                        |   1 -
agent/tool_registry.py                        |   4 +-
docker-compose.yml                            |  89 +---------------
docs/OPEN_WEBUI_SETUP.md                      |   2 +-
examples/start-sandbox.sh                     |   1 +
manifest.json                                 |  89 ++--------------
pyproject.toml                                |   8 +-
surfaces/open-webui/rasputin_function.py      |   6 +-
tests/test_capability_tools.py                |  33 +-----
tests/test_tool_registry.py                   |   5 +-
tools/coding_agent/index.py                   |  19 ++--
tools/coding_agent/manifest.json              |  11 +-
tools/mail/index.py                           |  34 ++----
tools/web_search/index.py                     |   6 +-
tools/web_search/manifest.json                |   2 +-
tools/webapp_builder/__init__.py              |   0 (deleted)
tools/webapp_builder/index.py                 |  69 ------------ (deleted)
tools/webapp_builder/manifest.json            |  20 ---- (deleted)
tools/wide_research/__init__.py               |   0 (deleted)
tools/wide_research/index.py                  | 145 -------------------------- (deleted)
tools/wide_research/manifest.json             |  29 ------ (deleted)
```
56 files changed, 108 insertions(+), 576 deletions(-)

## Acceptance criteria status
| # | Criterion | Status | Evidence path |
|---|-----------|--------|---------------|
| 1 | `pytest -v` → all green | PASS | phase-0-pytest.log |
| 2 | `ruff check .` → no errors | PASS | phase-0-ruff.log |
| 3 | Manifest tool count matches README/SKILL.md (16) | PASS | manifest.json |
| 4 | `pip install -e .` succeeds (no fake deps) | PASS | pyproject.toml cleaned |
| 5 | `docker compose --profile cpu config` valid | PASS | docker-compose.yml |
| 6 | `grep -r '/home/josh'` → no matches in code | PASS | grep check |
| 7 | `grep wide_research\|webapp_builder` → no matches | PASS | grep check |

## Test results
- Unit tests: 118 passed, 0 failed, 3 skipped
- pytest -v tail:
```
tests/test_tool_registry.py::test_load_tools_returns_callable_dict PASSED
tests/test_tool_registry.py::test_load_tool_metadata_returns_list PASSED
tests/test_loop_integration.py::test_run_goal_with_mocked_tools PASSED
================== 118 passed, 3 skipped in 3.44s ==================
```

## Lint
- ruff: clean (All checks passed)
- mypy: not run (phase brief does not require mypy for Phase 0)

## Cost
- LLM cost this phase: $0.00
- Sprint cost to date: $0.00
- Sprint budget: $25.00
- Headroom: $25.00

## Wall-clock
- Phase start: 2026-05-12T08:25:00Z
- Phase end: 2026-05-12T08:35:00Z
- Duration: ~10m

## Halt records
- None

## Out-of-spec changes
- Minor: Several tool index files had trailing import/lint issues fixed during the ruff pass (e.g., `tools/deliverables/index.py`, `tools/image_gen/index.py`, `tools/sandbox/index.py`). These were incidental lint fixes required to achieve `ruff check .` clean, not functional changes.
- Minor: `agent/` files had small import adjustments to keep tests green after tool deletions.

## Open questions / risks for next phase
- Phase 1 needs `load_tool_metadata()` implemented. The existing `agent/tool_registry.py` has an empty list comprehension at line 167-171. Skeleton is at `sprint/v0.5/skeletons/tool_metadata.py`.
- SearXNG port changed to 8889. If local SearXNG is running on 8888, Phase 1+ tests may need the new port.
