# PHASE-5 audit — Round 1

**Verdict:** ❌ **REVISE**
**Audited commit:** `72c5d25`
**Phase start SHA:** `72c5d25` (identical to HEAD — zero commits during PHASE-5)
**Auditor:** Strategic technical advisor (Opus)
**Date:** 2026-05-09

---

## Bottom line

PHASE-5 is a verification phase per the PHASE-2 waiver. The 6 extended **tool implementations are real and substantive** — that part of the evidence holds up. However, the rubric explicitly enumerates which checks may SKIP/PARTIAL under the hardware contingency (only 5-4, 5-5, 5-12, 5-13), and the gaps here go far beyond that envelope: Langfuse (5-8/5-9), promptfoo (5-10/5-11), and the multimodal demo (5-12) are entirely absent, and OpenClaw registration (5-7) is still blocked. Even the "PASS" claims for 5-1/5-2/5-3/5-6 do not satisfy the rubric's positive-path test requirements.

This is not a partial-APPROVE situation. The rubric's text is unambiguous: partial APPROVE is allowed *only* for video-gen / music-gen. Five further must-pass checks fail. Verdict: **REVISE**.

---

## Independent verification of evidence claims

| Evidence claim | Verified | Notes |
|---|---|---|
| 6 tool `index.py` files exist with real implementations (not stubs) | ✅ | `tools/{tts,stt,image_gen,video_gen,music_gen,memory}/index.py` — 57/58/172/169/36/58 LOC, all dispatch to real backends (httpx → Voxtral/ComfyUI/RASPUTIN, transformers, audiocraft) |
| `tests/test_extended_tools.py` exists | ✅ | 20 test cases across 6 tool classes |
| `pytest tests/ -q` → 75 passed, 3 skipped | ✅ | Reproduced locally in 3.28s |
| `agent/observability.py` is file-based, no Langfuse SDK | ✅ | 97 LOC; `_emit_span` writes JSON to `runlog/traces/`. No `import langfuse` anywhere in `agent/` or `tools/` |
| `evals/promptfoo.yaml` does not exist | ✅ | `evals/` directory does not exist |
| `examples/run-multimodal-demo.sh` does not exist | ✅ | `examples/` contains only `cross-tool-smoke.sh`, `run-demo.sh`, `start-sandbox.sh` |
| OpenClaw registration blocked (BACKLOG F-OpenClaw) | ✅ | Confirmed in `BACKLOG.md`; symlink-escape prevention; documented since PHASE-2 |
| Working tree clean | ✅ | `git status -s` empty |
| HEAD == 72c5d25 | ✅ | matches `runlog/PHASE-5-start.sha` exactly — **zero commits this phase** |

---

## Rubric checks (5-1 … 5-13)

| # | Evidence says | Audit verdict | Reasoning |
|---|---|---|---|
| 5-1 | ✅ PASS | ⚠️ **PARTIAL** | `tools/tts/index.py` is real (Voxtral + Kokoro fallback). But rubric requires *"Unit test produces non-empty .wav"*. `test_extended_tools.py::TestTTS` has only 3 negative-path tests (empty text, bad format, MODEL_UNAVAILABLE). No positive synthesis test exists. The rubric-required `test_synthesizes_wav_file_default_voice` and `test_kokoro_fallback_when_voxtral_unreachable` from the brief (5.1 step 3) are missing. |
| 5-2 | ✅ PASS | ⚠️ **PARTIAL** | `tools/stt/index.py` is real (Whisper + faster-whisper). Rubric requires transcription of a fixture audio. Only 2 negative-path tests exist (no audio_path, nonexistent file). The rubric-required `test_transcribes_fixture_wav` and `test_round_trip_tts_stt_recovers_text` are missing. Also: STT deviates from spec (Whisper instead of Canary-Qwen) — already in BACKLOG as F-A3, but undocumented in PHASE-5 evidence as required. |
| 5-3 | ✅ PASS | ⚠️ **PARTIAL** | `tools/image_gen/index.py` is real (ComfyUI workflow builder, 172 LOC). Rubric requires *"Unit test produces non-empty .png and image dimensions are within tolerance"*. Only 2 negative-path tests exist (empty prompt, ComfyUI unreachable). No positive test. |
| 5-4 | ⚠️ PARTIAL | ⚠️ **SKIP (acceptable)** | Hardware-contingent per phase brief. Implementation exists (169 LOC, real Wan workflow builder). However, `manifest.json` does **not** mark this tool with `"status": "deferred"` as the brief explicitly requires (sub-task 5.4 halt conditions; "Hardware contingency" §1). Tests are not `pytest.skip(reason="hardware deferred — see BACKLOG.md")`; they assert error codes. **Acceptable as SKIP only after manifest is annotated.** |
| 5-5 | ⚠️ PARTIAL | ⚠️ **SKIP (acceptable)** | Same shape as 5-4: real implementation (36 LOC), but manifest is not annotated `deferred` and tests are not skip-marked. Acceptable as SKIP only after manifest annotation. |
| 5-6 | ✅ PASS | ⚠️ **PARTIAL** | `tools/memory/index.py` is real (httpx → RASPUTIN MCP). Rubric requires *"Unit test stores a fact, retrieves it, searches for it"*. The 8 tests are all negative-path (invalid op, empty content, MCP unreachable). The rubric-required `test_store_then_retrieve` and `test_search_finds_stored_fact` are missing. |
| 5-7 | ❌ FAIL | ❌ **FAIL (BLOCKER per rubric, but pre-waived)** | OpenClaw registration confirmed blocked by symlink-escape prevention. Already deferred in BACKLOG.md as F-OpenClaw. **Same blocker as PHASE-2 (waived) and PHASE-3.** Joshua sign-off in PHASE-2-WAIVER.md does not extend automatically to PHASE-5; new explicit waiver needed. |
| 5-8 | ❌ FAIL | ❌ **BLOCKER** | Langfuse self-hosted not deployed. `curl -f $LANGFUSE_HOST/api/public/health` cannot succeed. Brief sub-task 5.7 (45 min) was not started. |
| 5-9 | ❌ FAIL | ❌ **BLOCKER** | No Langfuse SDK in `agent/observability.py`. `@observe` writes to `runlog/traces/` only. No traces in any Langfuse UI. |
| 5-10 | ❌ FAIL | ❌ **BLOCKER** | `evals/promptfoo.yaml` does not exist. `evals/` directory does not exist. Brief sub-task 5.8 (45 min) was not started. |
| 5-11 | ❌ FAIL | ❌ **BLOCKER** | No promptfoo run possible without 5-10. |
| 5-12 | ❌ FAIL | ⚠️ **PARTIAL (acceptable per rubric)** | `examples/run-multimodal-demo.sh` does not exist. Brief sub-task 5.9 (30 min) was not started. Per rubric, 5-12 *"may be PARTIAL with documented reason"* — but the partial-APPROVE clause only applies if 5-7 through 5-11 PASS. They don't. |
| 5-13 | ❌ FAIL | ⚠️ **PARTIAL (acceptable per rubric)** | No cost tracking possible without Langfuse (5-8/5-9). Same partial-APPROVE constraint as 5-12. |

**Score: 0 PASS / 6 PARTIAL / 5 BLOCKER / 2 conditional-PARTIAL**

---

## Universal checks (U-1 … U-10)

| # | Status | Notes |
|---|---|---|
| U-1 | ✅ | `git status --porcelain` empty |
| U-2 | ✅ | No commits in range — vacuously satisfied (PHASE-5-start == HEAD) |
| U-3 | ✅ | No new files written outside workspace |
| U-4 | ✅ | `pytest -q` → 75 passed, 3 skipped, no warnings |
| U-5 | ✅ | No diff range to scan; PHASE-2 waiver covered earlier scope |
| U-6 | ❌ | **ETA U-fail.** Phase target 7h, max 9h. Sub-tasks 5.7 (Langfuse), 5.8 (Promptfoo), 5.9 (multimodal) — total 120 min budgeted — were not attempted and not explained in evidence. Sub-tasks 5.4/5.5 hardware-deferral path was not followed (manifest not annotated). This is unexplained slippage on 5/9 sub-tasks. |
| U-7 | ✅ | No `runlog/HELP-PHASE-5-*` files (count = 0 ≤ 5) |
| U-8 | ⚠️ | Vacuously true (zero commits to cross-reference). All ✅ items in evidence trace to commits *prior* to PHASE-5-start.sha — i.e., from the PHASE-2 scope merge already covered by PHASE-2-WAIVER.md. Acceptable. |
| U-9 | ✅ | `grep -rn TODO kernel/ tools/ agent/` returns 0 hits |
| U-10 | ✅ | Evidence file is well-formed markdown with all required sections |

**U-checks: 1 BLOCKER (U-6)**

---

## Findings

### F-5-1 [BLOCKER] Langfuse stack absent (5-8, 5-9)
- **Evidence:** No `langfuse` import in `agent/`. No Docker compose for Langfuse. `agent/observability.py:1` still labeled *"PHASE-5 swaps to Langfuse"* — i.e., the swap never happened.
- **Why blocker:** 5-8 and 5-9 are explicit must-PASS checks for partial-APPROVE per the brief's "Hardware contingency" clause. The cost-tracking guarantee in 5-13 also depends on it.
- **Fix:** Sub-task 5.7 from the brief — deploy Langfuse via docker-compose, create project keys, swap `agent/observability.py` to use `langfuse.observe`. Effort: **Short (1–2h)** as scoped by brief.

### F-5-2 [BLOCKER] Promptfoo eval harness absent (5-10, 5-11)
- **Evidence:** `evals/` directory does not exist. No `promptfoo.yaml`. No `runlog/PHASE-5-promptfoo.json`.
- **Why blocker:** Both 5-10 and 5-11 are must-PASS for partial-APPROVE.
- **Fix:** Sub-task 5.8 from the brief — install promptfoo, author 5 golden tasks per `02-OSS-CAPABILITY-MATRIX.md` § "Eval", run them. Effort: **Short (1h)** as scoped by brief.

### F-5-3 [BLOCKER] Positive-path tests missing for 5-1, 5-2, 5-3, 5-6
- **Evidence:** `tests/test_extended_tools.py` is exclusively negative-path. No call exercises a working backend. Rubric language is explicit: "produces non-empty .wav", "transcribes a fixture audio", "produces non-empty .png and image dimensions are within tolerance", "stores a fact, retrieves it, searches for it".
- **Why blocker:** Without positive assertions, the implementations are *unverified at the contract level* — tests confirm only that the error-paths return the right error codes. Per rubric anti-pattern #5 ("Schema-only verified claims"), error-code-only assertions are explicitly disallowed as the sole evidence of capability.
- **Fix:** Add the rubric-named tests:
  - `test_synthesizes_wav_file_default_voice` (with Voxtral OR Kokoro reachable; gate on env var)
  - `test_kokoro_fallback_when_voxtral_unreachable`
  - `test_round_trip_tts_stt_recovers_text` (WER < 0.2)
  - `test_generates_png_for_simple_prompt` (with ComfyUI reachable; gate on env var, else `pytest.skip`)
  - `test_store_then_retrieve` and `test_search_finds_stored_fact` (with RASPUTIN reachable; gate on env var)
- **Effort:** **Short (2–3h)** including the env-gating plumbing.

### F-5-4 [BLOCKER] OpenClaw registration unwaived for PHASE-5 (5-7)
- **Evidence:** F-OpenClaw in BACKLOG.md notes the symlink-escape blocker. PHASE-2-WAIVER.md does not enumerate PHASE-5.
- **Why blocker:** 5-7 is a must-PASS for partial-APPROVE per the brief's contingency clause. The standing PHASE-2 waiver scopes only PHASE-2 (and retroactive 3-* / 5-* application — but does not waive blocked checks).
- **Fix:** Two acceptable paths:
  1. Joshua signs an extension to PHASE-2-WAIVER.md explicitly covering 5-7 (matches the precedent in PHASE-3 audit), OR
  2. Workaround: publish skill to `~/.openclaw/skills/` per BACKLOG note and verify `openclaw tool list` enumerates the 6 extended tools.
- **Effort:** **Quick (<30 min)** for path 1; **Unknown** for path 2.

### F-5-5 [IMPORTANT] Manifest does not mark 5-4/5-5 deferred
- **Evidence:** `grep '"status"' manifest.json` returns nothing. Brief sub-task 5.4 step 4, sub-task 5.5 step 4, and "Hardware contingency" §1 require `"status": "deferred"` annotation.
- **Why important (not blocker):** Without the annotation, the SKIP path the rubric provides for 5-4/5-5 is not formally claimed. Easy fix.
- **Fix:** Add `"status": "deferred"` to `video_gen` and `music_gen` entries in `manifest.json`. Add `pytest.skip(reason="hardware deferred — see BACKLOG.md")` to `TestVideoGen` and `TestMusicGen` classes (or convert assertions to `pytest.mark.skipif(not env_set)`).
- **Effort:** **Quick (<15 min)**.

### F-5-6 [IMPORTANT] Multimodal demo absent (5-12) and cost ceiling unmeasured (5-13)
- **Evidence:** `examples/run-multimodal-demo.sh` does not exist. No Langfuse cost data.
- **Why important (not blocker):** Rubric explicitly permits PARTIAL for these two — *if* the rest of the must-PASS items pass. They don't, so these collapse into the wider blocker pile but are not independently decisive.
- **Fix:** After F-5-1 and F-5-3 are resolved, sub-task 5.9 from the brief becomes mechanical (~30 min).
- **Effort:** **Quick (<45 min)**.

### F-5-7 [IMPORTANT] Phase ETA unexplained (U-6)
- **Evidence:** 3 of 9 sub-tasks (5.7, 5.8, 5.9) — totaling 120 min of the 7h budget — were not attempted. The evidence file does not explain *why*.
- **Fix:** Either (a) complete them, or (b) document in evidence why they were skipped (and update HELP-PHASE-5 if external blockers exist).
- **Effort:** **Quick (<10 min)** to document; otherwise rolled into above fixes.

---

## Anti-pattern scan

Re-running the rubric's anti-pattern checklist against the current implementations:

| # | Anti-pattern | Status |
|---|---|---|
| 1 | Tautological tests | ✅ Clean — extended tool tests assert against real error paths, not self-writes |
| 2 | Metadata-as-verification | ⚠️ **Caution.** Asserting `error.code == "MODEL_UNAVAILABLE"` when the model is *known* to be unavailable in the test env approaches this. The rubric calls this out at #5 ("Schema-only verified claims"). Folded into F-5-3. |
| 3 | Silent failure swallowing | ⚠️ **Already in BACKLOG (F-A1).** `tools/tts/index.py:33-34, 48-49`, `tools/stt/index.py:34-35` use `except Exception: pass`. PHASE-2 deferred this; should be resolved before PHASE-6. |
| 4 | Mocked unit tests labeled as integration | ✅ Clean — tests don't claim integration |
| 5 | Schema-only "verified" claims | ❌ **Triggered.** Evidence claims 5-1/5-2/5-3/5-6 PASS based on negative-path error codes alone. See F-5-3. |
| 6 | Phantom dependencies | ✅ Clean — Voxtral/ComfyUI/Wan/MusicGen/RASPUTIN are real services with documented endpoints |
| 7 | Untested error paths | ✅ Clean — error paths are in fact the *only* paths tested. (The inverse problem — F-5-3.) |
| 8 | Hardcoded `/home/josh/` paths | ✅ Clean in tools/agent (BACKLOG F-A2 covers the one remaining test-file instance) |
| 9 | Hidden side effects in imports | ✅ Clean — model loads are lazy inside `run()` |
| 10 | Deceptive console output | ✅ Clean |

**Net:** anti-patterns #2 and #5 are triggered together by F-5-3.

---

## Verdict reasoning

The brief's "Hardware contingency" clause is precise: *"5-1, 5-2, 5-3, 5-6, 5-7, 5-8, 5-9, 5-10, 5-11 must PASS; 5-4, 5-5 may be SKIP; 5-12, 5-13 may be PARTIAL with documented reason."*

Of the must-PASS nine:
- 5-1, 5-2, 5-3, 5-6 are PARTIAL (real impls but rubric-required positive tests absent — F-5-3)
- 5-7 is FAIL (no PHASE-5-scoped waiver — F-5-4)
- 5-8, 5-9 are FAIL (Langfuse never deployed — F-5-1)
- 5-10, 5-11 are FAIL (promptfoo never written — F-5-2)

Per rubric severity legend: *"A REVISE verdict requires at least one BLOCKER or two IMPORTANT findings."* This audit has **4 BLOCKERS and 3 IMPORTANTs.** APPROVE and PARTIAL APPROVE are both out of reach.

The good news: the substantive content of PHASE-5 — the 6 tool implementations — is real, sane, and thin enough to be reasonable. The gaps are infrastructure (Langfuse), eval scaffolding (promptfoo), and test coverage shape — all addressable in roughly the 5–6h that remained unspent in the original budget.

---

## Remediation roadmap (recommended order)

1. **F-5-5** (Quick, <15 min): annotate manifest + skip-mark video/music tests. Cheapest win; converts 5-4/5-5 to formal SKIP.
2. **F-5-4** (Quick, <30 min): get Joshua sign-off extending PHASE-2-WAIVER.md to 5-7, OR attempt the `~/.openclaw/skills/` publish workaround.
3. **F-5-3** (Short, 2–3h): add the rubric-named positive-path tests, env-gated where backends required. This is the largest single chunk of remaining work.
4. **F-5-1** (Short, 1–2h): execute sub-task 5.7 verbatim — Langfuse docker-compose, keys, swap `observability.py`.
5. **F-5-2** (Short, 1h): execute sub-task 5.8 verbatim — promptfoo install + 5 golden tasks.
6. **F-5-6** (Quick, <45 min): execute sub-task 5.9 — multimodal demo. Becomes trivial after the above.
7. **F-5-7** (Quick): update evidence file with ETA explanation.

**Total estimated remediation:** 5–7h — within the original 9h max ETA, just unspent.

---

## Re-audit budget

1 round consumed. **1 round remaining.** Per rubric, exhausting the budget without APPROVE escalates to ABORT.

---

## What's well-executed (keep)

- The six tool implementations are real backends, not stubs. None are phantom-deps.
- Negative-path coverage is thorough — error codes are consistent and tested.
- `agent/observability.py` placeholder is clean and clearly marked for swap.
- Working tree clean, tests fast (3.28s for 75+3), no hidden TODOs.
- BACKLOG.md is honest about deferred items.
- Evidence file is well-formed and self-aware about gaps (no false PASS claims for 5-7…5-13; the only over-claim is 5-1/5-2/5-3/5-6 which were marked PASS but lack rubric-required positive assertions).

The path back to APPROVE is mechanical, not conceptual.
