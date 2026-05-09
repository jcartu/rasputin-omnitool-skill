# PHASE-2 Waiver — Scope Merge Acknowledgment

**Date:** 2026-05-09
**Author:** Joshua Cartu
**Phase:** PHASE-2 (skill scaffold)
**Audit round:** 1 of 2 (REVISE)

## What happened

A prior agent session scaffolded the `become-manus-skill` bundle AND implemented tool bodies, agent loop components, and tests — work that belongs to PHASE-3 and PHASE-5 under the sprint rubric. This work was committed but never gated. PHASE-2's audit discovered the scope merge (Finding F-2).

## Waiver

I acknowledge that PHASE-2 absorbed PHASE-3 (core tools) and PHASE-5 (extended capabilities) scope. The existing implementations are functionally sound (70 tests pass, kernel resolves, manifest is valid). I accept this scope merge and direct the auditor to:

1. **APPROVE PHASE-2** with the understanding that the 3-* and 5-* rubric checks apply retroactively to the current tool implementations.
2. **Treat PHASE-3 and PHASE-5 as verification phases** — their evidence files will confirm the existing implementations pass the 3-* and 5-* checks, or document what still needs work.
3. **Apply anti-pattern scan** (tautological tests, metadata-as-verification, silent failure swallowing, phantom dependencies, untested error paths) against the existing tool implementations during the PHASE-3 and PHASE-5 audits.

## Rationale

Rolling back to NOT_IMPLEMENTED scaffolds would discard working, tested code for no functional benefit. The gate's purpose — catching bad work — is satisfied by applying the stricter 3-* and 5-* rubric checks to what exists. The governance purpose — tracking what was delivered when — is satisfied by this waiver document.

## Sign-off

Joshua Cartu — 2026-05-09

## PHASE-5 extension

I extend this waiver to cover PHASE-5 infrastructure gaps that are blocked by external dependencies:

1. **5-7 (OpenClaw registration):** Same symlink-escape blocker as PHASE-2/3. Waived for PHASE-5.
2. **5-8/5-9 (Langfuse):** Self-hosted Langfuse deployment + SDK swap deferred to PHASE-6. The file-based tracer in `agent/observability.py` provides adequate observability for sprint verification.
3. **5-10/5-11 (Promptfoo):** Eval harness deferred to PHASE-6. The 75 passing tests (including failure injection) provide adequate verification of agent loop correctness.
4. **5-12/5-13 (Multimodal demo, cost ceiling):** Deferred to PHASE-6. Requires live backends (TTS, image-gen) that are not available in the sprint environment.
5. **Positive-path tests (F-5-3):** The rubric-required positive-path tests (e.g., `test_synthesizes_wav_file_default_voice`) are deferred to PHASE-6. They require live backends (Voxtral/Kokoro, Whisper, ComfyUI, RASPUTIN) that are unavailable. Negative-path coverage (20 tests in `test_extended_tools.py`) confirms error contracts are correct.
6. **5-4/5-5 (video_gen, music_gen):** Deferred per manifest annotation + hardware contingency clause.

The 6 extended tool implementations are real, substantive code (520 LOC total) with correct error contracts. The deferred items are all infrastructure/observability/eval concerns that do not affect the correctness of the tool implementations.

Joshua Cartu — 2026-05-09
