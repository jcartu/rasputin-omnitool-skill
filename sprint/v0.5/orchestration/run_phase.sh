#!/usr/bin/env bash
# orchestration/run_phase.sh N
#
# Drives one phase end-to-end:
#   1. Check current state; advance/skip/halt as appropriate.
#   2. Create the phase branch if needed.
#   3. Print the phase brief for Sisyphus and pause for the work to happen.
#      (Sisyphus is invoked externally — OpenCode session — and is expected
#       to do the implementation, run tests, write evidence, and commit/push.)
#   4. Once `phase-N-evidence.md` and pushed commits exist, run review_with_opus.
#   5. On APPROVE, advance state. On REVISE, exit 1 to let the outer loop
#      give Sisyphus a chance to address findings. On ABORT, halt.
#
# Idempotent: re-running this script for the same phase is safe; it picks up
# wherever state.json says we are.

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "usage: $0 <phase>" >&2
    exit 2
fi

PHASE="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HANDOVER_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

BRANCH="sprint/v0.5-phase${PHASE}"
PHASE_BRIEF_PATTERN="${HANDOVER_DIR}/phases/PHASE-${PHASE}-*.md"

# locate the brief
PHASE_BRIEF=$(ls $PHASE_BRIEF_PATTERN 2>/dev/null | head -n1 || true)
if [[ -z "$PHASE_BRIEF" ]]; then
    echo "FATAL: no phase brief matching $PHASE_BRIEF_PATTERN" >&2
    exit 2
fi

EVIDENCE="sprint/v0.5/phase-${PHASE}-evidence.md"
HALT_FILE="sprint/v0.5/HALT-phase-${PHASE}.md"

echo "==[ run_phase $PHASE ]=================================================="
echo "Brief:      $PHASE_BRIEF"
echo "Branch:     $BRANCH"
echo "Evidence:   $EVIDENCE"

# ---- gate: have we already done this phase? ----
if python3 "$SCRIPT_DIR/state_helpers.py" is-approved "$PHASE"; then
    echo "Phase $PHASE already APPROVED; skipping."
    exit 0
fi
if python3 "$SCRIPT_DIR/state_helpers.py" is-halted "$PHASE"; then
    echo "Phase $PHASE is HALTED; see $HALT_FILE."
    exit 78
fi

# ---- gate: prior phase must be approved ----
if [[ "$PHASE" -gt 0 ]]; then
    PREV=$((PHASE - 1))
    if ! python3 "$SCRIPT_DIR/state_helpers.py" is-approved "$PREV"; then
        echo "FATAL: phase $PREV is not approved; cannot start phase $PHASE." >&2
        exit 2
    fi
fi

# ---- ensure branch ----
if ! git rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
    BASE="sprint/v0.5"
    if [[ "$PHASE" -eq 0 ]]; then
        BASE=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo main)
    fi
    git checkout -b "$BRANCH" "$BASE" || git checkout "$BRANCH"
else
    git checkout "$BRANCH"
fi

# Record the branch in state.json
python3 - <<EOF
import json, sys
from pathlib import Path
sys.path.insert(0, "$SCRIPT_DIR")
from state_helpers import read_state, write_state, set_phase_status

s = read_state()
s.setdefault("branches", {})["${PHASE}"] = "${BRANCH}"
write_state(s)
set_phase_status($PHASE, status="in_progress")
EOF

# ---- main work ----
# Sisyphus performs the implementation here. We expect:
#   - phase-N-evidence.md written to sprint/v0.5/
#   - at least one commit on the phase branch
#   - the branch pushed (best-effort; review still works without push)

if [[ -z "${RASPUTIN_OMNITOOL_NONINTERACTIVE:-}" ]]; then
    cat <<EOF

Sisyphus, your phase brief:

  $PHASE_BRIEF

When complete, ensure:
  - $EVIDENCE exists and follows rubrics/per-phase-rubric.md
  - At least one git commit on $BRANCH
  - Tests + lint logs in sprint/v0.5/phase-${PHASE}-*.log

This script will check for those artifacts and then call the Opus reviewer.

Press ENTER when ready to invoke review, or Ctrl-C to bail.
EOF
    read -r _
fi

# ---- pre-review sanity ----
if [[ ! -f "$EVIDENCE" ]]; then
    echo "FATAL: $EVIDENCE not found. Phase work incomplete." >&2
    exit 2
fi

if ! git diff --quiet HEAD; then
    echo "FATAL: uncommitted changes on $BRANCH. Commit before review." >&2
    exit 2
fi

# Best-effort push
git push -u origin "$BRANCH" || echo "(push failed; review can still proceed)"

# ---- review ----
python3 "$SCRIPT_DIR/state_helpers.py" set-phase "$PHASE" awaiting_review

set +e
bash "$SCRIPT_DIR/review_with_opus.sh" "$PHASE"
RC=$?
set -e

case "$RC" in
    0)
        echo ""
        echo "==[ phase $PHASE APPROVED — advancing ]=========================="
        python3 - <<EOF
import sys
sys.path.insert(0, "$SCRIPT_DIR")
from state_helpers import update_state
update_state(current_phase=$PHASE + 1)
EOF
        exit 0
        ;;
    1)
        echo ""
        echo "==[ phase $PHASE REVISE — address findings then re-run ]========"
        # Caller (or outer loop) re-invokes run_phase.sh after Sisyphus patches.
        exit 1
        ;;
    2)
        echo ""
        echo "==[ phase $PHASE ABORT — write HALT and stop ]=================="
        if [[ ! -f "$HALT_FILE" ]]; then
            cat > "$HALT_FILE" <<MD
# HALT phase ${PHASE}

Reviewer returned ABORT (or two consecutive REVISE rounds).

See:
- sprint/v0.5/review-${PHASE}.json — full verdict + findings
- $EVIDENCE — evidence submitted
- $PHASE_BRIEF — original brief

Sisyphus should NOT roll back. Wait for Joshua.
MD
        fi
        exit 78
        ;;
    *)
        echo "Unexpected review exit code: $RC" >&2
        exit 78
        ;;
esac
