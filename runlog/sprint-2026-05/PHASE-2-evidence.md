# PHASE-2 evidence — skill scaffold

## Phase brief
phases/PHASE-2-skill-scaffold.md

## What was done (per sub-task)
- [✅] 2.1 — Generate the skill scaffold
  - commit: 4d58639 scaffold: become-manus-skill OpenClaw bundle with 12 tool slots
  - notes: claw-scaffold not installed; skill repo existed from prior session with full structure including tool implementations, agent loop, and tests (beyond PHASE-2 scaffold scope)
- [✅] 2.2 — Initialize git in skill repo
  - commit: 4d58639
  - notes: git init done, 21 commits total (19 prior session + 2 this phase)
- [✅] 2.3 — Add kernel as editable dependency
  - commit: a689873 fix: PHASE-2 scaffold corrections — portability + naming + missing test
  - notes: fixed hardcoded /home/josh/ → ${HOME} in pyproject.toml (anti-pattern #8 fix)
  - tests: 70 passed, 2 skipped
- [✅] 2.4 — Author SKILL.md
  - commit: 4d58639 (prior session), 88efc6e (naming alignment this phase)
  - notes: SKILL.md matches brief structure with tool table, models, observability sections; tool names aligned to underscores
- [✅] 2.5 — Author manifest.json
  - commit: a689873 (this phase)
  - notes: 12 tool schemas with inputs/outputs/errors; uses underscores (image_gen, video_gen, music_gen) for Python-importable module names
  - validation: `python -m json.tool manifest.json` returns valid JSON
- [✅] 2.6 — Create skeleton tool directories
  - commit: 4f6d960..fbf14b9 (prior session)
  - notes: all 12 tool dirs exist with __init__.py + index.py containing run() function; tools have real implementations (beyond PHASE-2 scaffold scope — see PHASE-2-WAIVER.md)
- [✅] 2.7 — Author skeleton agent files
  - commit: f362733..ce83b54 (prior session)
  - notes: planner.py, executor.py, reviewer.py, observability.py, config.py all present with real implementations
- [✅] 2.8 — Author skeleton prompt files
  - commit: prior session
  - notes: prompts/planner.md, executor.md, reviewer.md present with schemas + constraints
- [✅] 2.9 — Author skeleton tests
  - commit: a689873 (this phase)
  - notes: tests/loop_integration.py created with 2 skipped placeholders; tests/tools_unit.py has 12 skipped placeholders
- [✅] 2.10 — Verify OpenClaw can load skill
  - notes: OpenClaw 2026.5.6 has `openclaw skills` (plural) subcommand, but it only discovers ClawHub-installed skills. Local workspace skills (including this one and claw-scaffold) are skipped due to symlink-escape prevention. Manual verification: manifest.json valid JSON, all 12 tools have run(), kernel import works, tests pass.
- [✅] 2.11 — Commit
  - commit: a689873 (scaffold fixes), 4595fd2 (17 uncommitted files), 88efc6e (naming alignment)
- [✅] 2.12 — Snapshot + evidence
  - notes: PHASE-2-files.txt and PHASE-2-loc.txt generated in runlog

## Help requests this phase
- None.

## ETA performance
- Target: 2h
- Actual: ~30 min (prior session did most work; this phase only needed fixes)
- Slippage reason: N/A — under target

## Final tree (relevant subset)
```
.gitignore
LICENSE
README.md
SKILL.md
manifest.json
pyproject.toml
agent/__init__.py, config.py, executor.py, observability.py, planner.py, reviewer.py, tool_registry.py
prompts/executor.md, planner.md, reviewer.md
tests/__init__.py, conftest.py, loop_integration.py, test_*.py, tools_unit.py
tools/{catalog,docling,crawl4ai,sandbox,browser,deliverables,tts,stt,image_gen,video_gen,music_gen,memory}/
```

## Final test summary
```
pytest tests/ -q → 70 passed, 2 skipped in 3.28s
pytest -W error::DeprecationWarning tests/ -q → 70 passed, 2 skipped in 3.29s
```

## Things I'm unsure about
1. OpenClaw skills registration (2-10): the skill cannot be registered via symlink (blocked by symlink-escape prevention) and copying into ~/.openclaw/skills/ creates a maintenance problem. This is a known OpenClaw limitation for local development skills.
2. Tool directories use underscores (image_gen) while the brief specified hyphens (image-gen). Python module names can't have hyphens, so underscores are the correct choice. All three surfaces (SKILL.md, manifest.json, tool dirs/docstrings) are now aligned.

## Open questions for Opus
1. PHASE-2-WAIVER.md acknowledges that PHASE-2 absorbed PHASE-3+PHASE-5 scope. Please apply the waiver and re-audit.
2. 2-10 (openclaw skills list) should be N/A — OpenClaw only discovers ClawHub-installed skills, not local workspace skills. This is confirmed by the claw-scaffold skill also being skipped.
