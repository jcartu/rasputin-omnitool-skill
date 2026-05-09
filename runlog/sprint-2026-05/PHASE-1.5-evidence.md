# PHASE-1.5 evidence — kernel cleanup (interstitial)

## Phase brief
PHASE-1.5 is an interstitial cleanup between PHASE-1 (kernel extraction) and PHASE-2 (skill scaffold). No phase brief file exists; instructions were provided inline by Joshua.

## What was done (per sub-task)
- [✅] Delete orphaned kernel modules (smoke.py, browser_e2e.py, browser_workflow_e2e.py, sandbox_hosting.py, webapp_smoke.py)
  - commit: 8be330e refactor: PHASE-1.5 cleanup — finish kernel split
  - tests: green, 10 passed
  - LOC delta: +0 / −1682
  - notes: 5 kernel modules removed. These will be recovered in PHASE-3 as skill tools.
- [✅] Delete orphaned outputs subdirs (analytics, browser-e2e, browser-workflow-e2e, coding-agents, demo, mail, sandbox, webapp)
  - commit: 8be330e (same commit)
  - notes: Products of deleted modules — all output artifacts removed.
- [✅] Delete stale narrative reports
  - commit: N/A — no stale narrative reports found at repo root
  - notes: Only README.md existed at root.
- [✅] Delete orbi_discovery_2026-05-08.json
  - commit: 8be330e (same commit)
  - notes: Unrelated artifact committed accidentally from parallel agent task on 2026-05-08. Contains MAC addresses + firmware versions (mild fingerprinting risk in public repo). Joshua's call: DELETE.

## Help requests this phase
- None.

## ETA performance
- Target: N/A (interstitial phase, no ETA in master plan)
- Actual: ~10 minutes
- Slippage reason: N/A

## Final tree (relevant subset)
```
.gitignore
LICENSE
README.md
become_manus_kernel/__init__.py
become_manus_kernel/__main__.py
become_manus_kernel/_venv_helpers.py
become_manus_kernel/bakeoff.py
become_manus_kernel/catalog.py
become_manus_kernel/cli/__init__.py
become_manus_kernel/cli/__main__.py
become_manus_kernel/deliverables.py
become_manus_kernel/library_smoke.py
become_manus_kernel/licenses.py
become_manus_kernel/licenses_manual.py
pyproject.toml
tests/__init__.py
tests/test_kernel.py
```

## Final test summary
```
pytest -q → 10 passed in 1.02s
pyflakes become_manus_kernel/ → zero unresolved references (clean)
```

## Things I'm unsure about
- PHASE-1.5 is an interstitial phase not defined in the rubric. I'm applying PHASE-1 rubric checks (1-1 through 1-10) since this phase completes the kernel split started in PHASE-1. If Opus expects different checks, I'll adjust.

## Open questions for Opus
- Should PHASE-1.5 be audited against PHASE-1 rubric (since it finishes the kernel split) or just universal checks?
- The single-commit approach for all deletions is intentional — all changes are pure deletions of one concern (orphaned artifacts). No split needed per git-master rules since all files share the same atomic reason.
