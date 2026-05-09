# PHASE-2 Gate Audit — Skill Scaffold

**Auditor:** Opus 4.7
**Date (UTC):** 2026-05-09
**Phase commit range:** `4d58639..a689873` (skill repo `~/workspace/become-manus-skill`)
**Phase start sha:** `4d58639560554efcf55aa7e20173c5bc52a62d9c`
**HEAD:** `a689873`
**Re-audit round:** 1 of 2
**Verdict:** **REVISE**

---

## TL;DR

The skill bundle is structurally sound — it loads, the kernel resolves as an editable dependency, the manifest declares all 12 tool slots, all required scaffold files are present, and `pytest` reports 70 passed / 2 skipped. **However, the gate cannot APPROVE** because three universal-check violations are present and one rubric check (2-6) is materially violated by scope creep.

The blockers are mechanical and fixable in well under an hour. Prior-session work produced real implementations, real tests, and real docs that exceed the scaffold brief — that work has merit but it is **not what PHASE-2 was scoped to deliver**, and it has masked problems (uncommitted edits, deviating doc claims, an evidence file that is wrong about openclaw tooling) that the gate is specifically designed to catch.

---

## Verdict: REVISE

A REVISE verdict requires ≥1 BLOCKER or ≥2 IMPORTANT. This audit finds **2 BLOCKERS, 3 IMPORTANT, 4 MINOR**.

Re-audit budget remaining after this round: **1 round**.

---

## Universal checks

| ID | Check | Status | Evidence |
|---|---|---|---|
| U-1 | Working tree clean | ❌ **FAIL** | `git status --porcelain` shows **17 modified files** in `~/workspace/become-manus-skill` (README.md, SKILL.md, SPRINT.md, agent/config.py, 5 test files, 8 tool index.py files). HEAD is `a689873` but the tree has uncommitted edits totaling ~724 insertions / 198 deletions. |
| U-2 | Meaningful commit messages | ✅ PASS | All 20 commits in the phase range use conventional prefixes (`scaffold:`, `feat:`, `fix:`, `docs:`, `test:`, `chore:`). No `wip`/`tmp`/`asdf`. |
| U-3 | No files outside workspace | ✅ PASS | All artifacts under `~/workspace/become-manus-skill/`. Sprint runlog under `~/workspace/become-manus-sprint/runlog/` (expected). |
| U-4 | Tests pass with no deprecation warnings | ⚠️ PARTIAL | `pytest tests/ -q` → 70 passed, 2 skipped in 3.27s. Not run with `-W error::DeprecationWarning`; no `WARNINGS.md` exists. Treating as PASS-with-note since pytest exit was 0; flagging as MINOR. |
| U-5 | No secrets/keys committed | ✅ PASS | Diff scan over `4d58639..a689873` reveals no `sk-`, `api_key=`, `token=`, or `password=` patterns introduced. |
| U-6 | ETA met or slippage explained | ✅ PASS | Target 2h, actual ~30 min (most work pre-existed). Explained in evidence. |
| U-7 | Help-request count ≤ 5 | ✅ PASS | Zero help requests this phase. |
| U-8 | Evidence checkmarks have commits | ⚠️ PARTIAL | Sub-tasks 2.1, 2.2, 2.4, 2.6, 2.7, 2.8 are claimed as ✅ but the evidence attributes them to a "prior session" that pre-dates `PHASE-2-start.sha=4d58639` (which IS the scaffold commit `4d58639 scaffold: become-manus-skill OpenClaw bundle with 12 tool slots`). The pre-existing work that the evidence references happened *between* `4d58639` and `c0dc933` — i.e., **inside the phase window**, not before it. The bookkeeping is muddled but the commits do exist. |
| U-9 | No untracked TODOs | ✅ PASS | `grep -rn TODO tools/ agent/ --include='*.py'` returns zero hits. |
| U-10 | Evidence well-formed | ⚠️ PARTIAL | Markdown parses; required sections present. **However, the evidence contains a factual error** (see Finding F-3): it claims OpenClaw 2026.5.6 has no `skill` subcommand; in fact `openclaw skills` (plural) exists with `list`, `info`, `check` subcommands and was not attempted. |

**U-check verdict:** U-1 is a hard fail. U-4, U-8, U-10 are partial. Per rubric, "If any U-check fails, the verdict is REVISE at minimum." Confirmed.

---

## PHASE-2 specific checks

| ID | Check | Status | Evidence |
|---|---|---|---|
| 2-1 | `become-manus-skill/` exists as sibling of `become-manus/` | ✅ PASS | Both exist under `~/workspace/`. Kernel imports from `/home/josh/workspace/become-manus/become_manus_kernel/__init__.py`. |
| 2-2 | `SKILL.md` well-formed and parseable by OpenClaw | ⚠️ PARTIAL | `SKILL.md` is well-formed markdown matching the brief. **OpenClaw cannot validate it directly** — the bundled `openclaw skills` command operates on the workspace skills registry (`~/.openclaw/skills/`), not arbitrary directories. The skill is not registered in that registry, so `openclaw skills info become-manus-skill` returns "not found." The brief's exact command (`openclaw skill validate`) does not exist. Treating as PASS for "well-formed" but flagging the verification gap. |
| 2-3 | `manifest.json` declares all 12 tool slots with placeholder bodies | ✅ PASS (schema) / ❌ FAIL (placeholder bodies) | All 12 tools enumerated: `catalog, docling, crawl4ai, sandbox, browser, deliverables, tts, stt, image_gen, video_gen, music_gen, memory`. JSON parses. Schema fields complete. The "placeholder bodies" half of this check is violated — see 2-6. |
| 2-4 | `pyproject.toml` declares kernel as editable dep → `../become-manus` | ✅ PASS | `become_manus_kernel @ file:///${HOME}/workspace/become-manus`. The `${HOME}` substitution diverges from the brief's literal `../become-manus` but is a portability improvement and resolves to the same path. Acceptable. |
| 2-5 | `pip install -e .` succeeds and pulls kernel | ✅ PASS | `pip show become_manus_kernel` reports `Editable project location: /home/josh/workspace/become-manus`. `python -c "import become_manus_kernel"` succeeds. |
| 2-6 | Each `tools/*/index.py` has contract docstring + no-op body returning NOT_IMPLEMENTED | ❌ **FAIL** | `grep -rn NOT_IMPLEMENTED tools/ --include='*.py'` returns **zero hits**. All 12 tools contain real implementations (httpx ComfyUI workflow builders, Playwright drivers, kernel wrappers). The brief is explicit on this (line 385): *"a no-op body returning `{\"error\": {\"code\": \"NOT_IMPLEMENTED\", ...}}`"*. The brief also explicitly warns (line 837): *"Don't be tempted to start writing tool bodies. Resist."* This warning was ignored. |
| 2-7 | `prompts/{planner,executor,reviewer}.md` present with skeleton | ✅ PASS | All three present. |
| 2-8 | `tests/tools_unit.py` and `tests/loop_integration.py` present with skip markers | ✅ PASS | Both present; `loop_integration.py` has two `@pytest.mark.skip(reason="wired in PHASE-4")` markers (verified by the 2 skipped count). `tools_unit.py` is present (not opened in detail; collection passes). |
| 2-9 | `agent/__init__.py` + planner/executor/reviewer/observability.py present | ✅ PASS | All five present plus extras (`config.py`, `tool_registry.py`). The brief permitted `config.py`; `tool_registry.py` is scope creep but a benign addition. |
| 2-10 | `openclaw skill list` shows the skill | ❌ **FAIL** (different reason than evidence claims) | The evidence claims this is N/A because "OpenClaw 2026.5.6 has no skill subcommand." **This is wrong.** `openclaw skills list` (plural) exists and works. I ran it: the skill does not appear (45 of 72 ready, none named `become-manus`). The skill is not installed into the OpenClaw skills registry. The check fails because the skill is not discoverable, not because the tooling is missing. |

---

## Findings

### F-1 [BLOCKER] Working tree is dirty — 17 uncommitted files

**Severity:** BLOCKER
**Rubric:** U-1
**Evidence:**
```
$ git status --porcelain | wc -l
17
$ git diff --stat HEAD | tail -3
17 files changed, 724 insertions(+), 198 deletions(-)
```

Modified files include 8 tool implementations (`tools/{browser,crawl4ai,image_gen,memory,music_gen,sandbox,stt,video_gen}/index.py`), 5 test files, `agent/config.py`, `README.md`, `SKILL.md`, `SPRINT.md`. None of these edits are committed.

**Why this is a blocker:** U-1 is non-negotiable. A dirty tree at gate time means the auditor cannot reason about what actually shipped vs. what is sitting in the working copy. It also means re-running tests and re-running validation produces results that are inconsistent with the commit log.

**Required fix:** Either commit the changes with conventional messages (and re-run the gate against the new HEAD), or `git restore` them. Decide which by reading what each diff actually contains — they appear to be substantive (e.g., README adds a 60-line "Why this exists" section; `image_gen/index.py` gains a 100-line `_build_workflow` helper).

**Effort:** Quick (<1h).

---

### F-2 [BLOCKER] Rubric check 2-6 violated — tools have real bodies, not NOT_IMPLEMENTED

**Severity:** BLOCKER
**Rubric:** 2-6
**Evidence:**
```
$ grep -rn NOT_IMPLEMENTED tools/ --include='*.py'
(no output)
```
Every tool — including `image_gen/index.py` (172 lines, full ComfyUI workflow with KSampler/VAEDecode/SaveImage nodes, httpx polling loop), `browser/index.py` (Playwright driver), `crawl4ai/index.py`, `docling/index.py`, etc. — contains a real implementation.

**Why this is a blocker:** The rubric is explicit and the brief warns against exactly this on line 837. The gate exists to enforce phase boundaries; if PHASE-2 gates pass while delivering PHASE-3+PHASE-5 work, every subsequent phase audit becomes harder because the "what changed in this phase" boundary is gone.

**This is a governance problem, not a code-quality problem.** The implementations themselves may well be good (70 tests pass against them). The issue is that they were merged under PHASE-2 instead of PHASE-3/PHASE-5, where the rubric checks would actually scrutinize them (e.g., 3-* checks for core tool integration tests that hit real boundaries).

**Two paths forward** (Joshua picks):

1. **Honor the brief literally (REVISE path).** Hard-reset the skill repo to `4d58639` (the actual scaffold commit), re-do PHASE-2 with NOT_IMPLEMENTED placeholders, then re-run PHASE-3/PHASE-5 to land the implementations under the correct phase audits. This wastes the existing implementations' commit history but makes the audit trail clean. Effort: Medium (1-2 days).

2. **Acknowledge scope-merge and re-frame (APPROVE-WITH-WAIVER path).** Joshua issues a written waiver acknowledging that PHASE-2 absorbed PHASE-3 and PHASE-5 scope, and the audit retroactively applies the 3-* and 5-* checks here. This requires the auditor (next round) to verify those checks too — the present audit cannot do so because the rubric for them was not consulted in this scope. Effort: Short (1-4h, mostly re-audit).

I recommend path 2 if Joshua values the existing implementations, with the explicit understanding that PHASE-3 and PHASE-5 then become near-no-ops with their own evidence files explaining the early-merge.

**Required fix (regardless of path):** A waiver from Joshua, captured in `runlog/PHASE-2-WAIVER.md` or equivalent, OR a hard reset.

---

### F-3 [IMPORTANT] Evidence file contains a factual error about OpenClaw tooling

**Severity:** IMPORTANT
**Rubric:** U-10, 2-10
**Evidence:** The evidence file states:

> `2.10 — Verify OpenClaw can load skill (UNAVAILABLE — OpenClaw 2026.5.6 has no "skill" subcommand)`

I ran `openclaw --help` on this machine. There is no `skill` (singular) command, but there is `skills` (plural):

```
skills *             List and inspect available skills
  Subcommands: check, info, install, list, search, update
```

`openclaw skills list` works and produces a 72-skill table. `openclaw skills check` works and produces a missing-requirements list. `openclaw skills info become-manus-skill` returns `Skill "become-manus-skill" not found.`

So 2-10 is verifiable — and it **fails** because the skill isn't registered in the OpenClaw skills root (`~/.openclaw/skills/`), not because the tooling doesn't exist.

**Why this matters:** the evidence asserted N/A on a check that is actually verifiable, and the verifiable result is FAIL. This is the second-order problem the gate is designed to catch (U-10: "the evidence file itself is well-formed" — a file with a wrong factual claim is not well-formed in the relevant sense).

**Required fix:** Update evidence to reflect the actual command (`openclaw skills`), document the registration gap (the skill needs to be linked into `~/.openclaw/skills/become-manus-skill` or installed via the OpenClaw mechanism — claw-scaffold normally handles this), and either register it or capture the gap as an explicit deferred item with sign-off.

**Effort:** Quick (<30 min) — likely a `ln -s ~/workspace/become-manus-skill ~/.openclaw/skills/become-manus-skill` plus re-running `openclaw skills check` and capturing the output.

---

### F-4 [IMPORTANT] Tool dir naming diverges from brief; the divergence is correct, but it was not flagged

**Severity:** IMPORTANT (because it's a contract change)
**Rubric:** 2-3
**Evidence:** The brief mandates tool names `image-gen`, `video-gen`, `music-gen` (hyphenated, lines 308, 323, 336 of the brief and line 158-160 of `SKILL.md`'s rendered table). The manifest now uses `image_gen`, `video_gen`, `music_gen` (underscored). The `SKILL.md` table still shows hyphens. The directory names match the manifest (underscores).

**Why this matters:** Python cannot import a module named `image-gen`, so the underscores are necessary if the manifest is meant to map 1:1 to a Python module path. But this is a contract change from what the brief specified, and it produces three places of inconsistency:
- `SKILL.md` table → hyphens
- `manifest.json` → underscores
- `tools/<dir>/` → underscores
- Tool docstrings (e.g., `tools/image_gen/index.py` line 1) → still say `image-gen`

If OpenClaw's manifest schema treats the `name` field as the user-facing tool ID, downstream prompts/docs that say `image-gen` will fail to resolve when planner/executor look up the tool.

**Required fix:** Pick one (underscores, since Python forces it) and align all three surfaces. Update `SKILL.md` table rows for `image-gen`/`video-gen`/`music-gen` → `image_gen`/`video_gen`/`music_gen`. Update tool docstrings. Add a brief note to evidence explaining the deviation from the brief.

**Effort:** Quick (<30 min).

---

### F-5 [IMPORTANT] Phase boundary metadata is inconsistent across runlog

**Severity:** IMPORTANT
**Rubric:** U-8, U-10
**Evidence:** `runlog/PHASE-2-start.sha` contains `4d58639560554efcf55aa7e20173c5bc52a62d9c`. That sha IS the scaffold commit (`4d58639 scaffold: become-manus-skill OpenClaw bundle with 12 tool slots`). The evidence file describes 2.1, 2.2, 2.4, 2.6, 2.7, 2.8 as completed in a "prior session" — but the start sha is the prior session's first commit, so the work is *inside* the phase window, not before it.

Additionally, the runlog directory already contains `PHASE-3-end.sha`, `PHASE-3-start.sha`, `PHASE-3-files.txt`, and `PHASE-4-start.sha`. These are PHASE-3 and PHASE-4 artifacts created before PHASE-2 was even gated. This corroborates F-2: the prior session ran ahead through multiple phases without gates.

**Required fix:** Reconcile the evidence narrative with the actual git history. State plainly: "The skill repo was scaffolded and most tool/agent work landed in commits `4d58639..c0dc933` during a prior session that ran ahead of the gate. PHASE-2's nominal scope was scaffold-only; commits beyond the scaffold are de facto PHASE-3/PHASE-5 work and require either a waiver (F-2 path 2) or rollback (F-2 path 1)." Also clearly mark the PHASE-3 and PHASE-4 runlog files as pre-gate artifacts.

**Effort:** Quick (<30 min).

---

### F-6 [MINOR] Anti-pattern #8 — hardcoded path was present and is now fixed; verify there are no others

**Severity:** MINOR (already fixed)
**Rubric:** Anti-pattern #8 (hardcoded `/home/josh/` paths)
**Evidence:** Commit `a689873` corrected `pyproject.toml` from `file:///home/josh/workspace/become-manus` → `file:///${HOME}/workspace/become-manus`. Good catch by Sisyphus. `grep -rn /home/josh tools/ agent/ --include='*.py'` returns zero hits in source files (only `__pycache__` binary matches, which are gitignored). Confirmed clean.

**No fix required.** Noting as MINOR purely so the audit trail records that the anti-pattern was inspected and resolved.

---

### F-7 [MINOR] U-4 not run with `-W error::DeprecationWarning`

**Severity:** MINOR
**Rubric:** U-4
**Evidence:** `pytest tests/ -q` exits 0 with 70 passed, 2 skipped. The rubric specifies running with `-W error::DeprecationWarning` or equivalent. This was not done, so deprecated-API warnings (if any exist) are unverified.

**Required fix:** Run `pytest -W error::DeprecationWarning tests/`. If warnings appear, either fix them or log in `WARNINGS.md`.

**Effort:** Quick (<10 min).

---

### F-8 [MINOR] `SKILL.md` adds optional sections beyond the brief

**Severity:** MINOR
**Rubric:** None directly; informational
**Evidence:** Current `SKILL.md` includes `## Quick invocation`, `## Required environment variables`, and a `Status` column on the tools table that the brief did not specify. It also drops the `## Cost ceiling` section the brief specified. These are quality improvements but they are scope drift from the brief.

**Required fix:** None required — flagging only because if Joshua wants strict-brief adherence, this is a place to align. The "available" status claim on every tool is now misleading given that 2-6 expected NOT_IMPLEMENTED bodies — but if the F-2 waiver path is taken, "available" becomes accurate.

---

### F-9 [MINOR] PHASE-2 sub-task 2.12 (snapshot) only partially completed

**Severity:** MINOR
**Rubric:** U-8
**Evidence:** Brief 2.12 requires `runlog/PHASE-2-files.txt` and `runlog/PHASE-2-loc.txt`. `PHASE-2-files.txt` exists; `PHASE-2-loc.txt` does not exist (only PHASE-0 has loc files in the runlog).

**Required fix:** Run the snapshot command from the brief: `wc -l agent/*.py tools/*/index.py prompts/*.md tests/*.py | tee ~/workspace/become-manus-sprint/runlog/PHASE-2-loc.txt`.

**Effort:** Quick (<5 min).

---

## Anti-pattern scan

| # | Anti-pattern | Status |
|---|---|---|
| 1 | Tautological tests | Not audited (would require 3-* rubric scope; deferred per F-2) |
| 2 | Metadata-as-verification | Not flagged in scaffold scope |
| 3 | Silent failure swallowing | Not audited at scaffold scope |
| 4 | Mocked unit tests labeled integration | Not audited at scaffold scope |
| 5 | Schema-only "verified" claims | Not flagged |
| 6 | Phantom dependencies | Not flagged in scaffold scope |
| 7 | Untested error paths | Not audited at scaffold scope |
| 8 | Hardcoded `/home/josh/` paths | Was present, fixed in `a689873`. Clean now. (F-6) |
| 9 | Hidden side effects in imports | Spot-checked tool indexes; clean. |
| 10 | Deceptive console output | Not flagged |

Anti-patterns 1, 3, 4, 6, 7 are deferred because the rubric for tools is in PHASE-3/PHASE-5. If F-2 path 2 (waiver) is taken, the next-round auditor MUST run these against the existing tool implementations.

---

## What needs to happen for re-audit APPROVE

**Mandatory (BLOCKERS):**

1. **F-1**: Resolve the 17 uncommitted files. Either commit them (with phase justification) or restore them. Re-run `git status --porcelain` to confirm clean.
2. **F-2**: Decide path (rollback vs. waiver). If waiver, write `runlog/PHASE-2-WAIVER.md` signed by Joshua acknowledging that PHASE-2 absorbed PHASE-3+PHASE-5 scope and that the next audit round will apply the 3-* and 5-* rubrics here.

**Mandatory (IMPORTANTs):**

3. **F-3**: Correct the evidence's claim about `openclaw skill` vs `openclaw skills`. Register the skill in the OpenClaw skills registry (likely a symlink into `~/.openclaw/skills/`) so `openclaw skills info become-manus-skill` resolves. Capture the output in evidence.
4. **F-4**: Align tool naming across `SKILL.md` ↔ `manifest.json` ↔ `tools/<dir>/` ↔ tool docstrings. Underscores everywhere (since Python).
5. **F-5**: Reconcile evidence narrative with actual git history. Mark pre-existing PHASE-3/PHASE-4 runlog artifacts as out-of-band.

**Recommended (MINORs):**

6. **F-7**: Re-run pytest with `-W error::DeprecationWarning`.
7. **F-9**: Generate `runlog/PHASE-2-loc.txt`.

**Total effort to re-audit:** ~2-4 hours if waiver path; ~1-2 days if rollback path.

---

## Note to Joshua

The skill is functionally further along than PHASE-2 asked for, and the work that exists looks competent. The audit is not REVISE because the work is bad — it's REVISE because **a gated sprint loses its value the moment a phase boundary is silently crossed**. The whole point of the rubric is that "this is what was supposed to happen by now" can be checked against "this is what actually happened." When those diverge, you have to either roll back or sign a waiver — what you cannot do is APPROVE and pretend the divergence didn't happen.

The simplest path is the waiver path (F-2 path 2). It costs ~3-4 hours of re-audit work but preserves the implementations. The rollback path is more honest to the original sprint structure but throws away real working code.

If you take the waiver path, the next-round auditor needs the PHASE-3 and PHASE-5 rubric checks applied to the current state of the tools — those checks include real-boundary integration tests, error-path coverage, and phantom-dependency scans that this audit deliberately did not run.

— Opus 4.7
