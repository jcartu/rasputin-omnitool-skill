#!/usr/bin/env bash
# orchestration/review_with_opus.sh N
#
# Submit phase N evidence to Opus and act on the verdict.
# Exit codes:
#   0  — APPROVE; advance the phase status, ready to move on
#   1  — REVISE; caller should address findings and re-invoke
#   2  — ABORT;  caller should write HALT-phase-N.md, halt sprint
#   78 — input/API error; caller should retry after fixing the cause

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "usage: $0 <phase>" >&2
    exit 2
fi

PHASE="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EVIDENCE_PATH="sprint/v0.5/phase-${PHASE}-evidence.md"

if [[ ! -f "$EVIDENCE_PATH" ]]; then
    echo "FATAL: missing $EVIDENCE_PATH; cannot review" >&2
    exit 78
fi

echo "==[ Opus review: phase ${PHASE} ]=========================================="
echo "Evidence:  $EVIDENCE_PATH"
echo "Model:     ${RASPUTIN_OMNITOOL_REVIEWER_MODEL:-claude-opus-4-7}"
echo ""

# Bump review counter
REVIEW_N=$(python3 "$SCRIPT_DIR/state_helpers.py" increment-review "$PHASE")
echo "Review attempt: $REVIEW_N"

python3 "$SCRIPT_DIR/opus_review.py" --scope phase --phase "$PHASE"
RC=$?

VERDICT_FILE="sprint/v0.5/review-${PHASE}.json"
if [[ -f "$VERDICT_FILE" ]]; then
    echo ""
    echo "Verdict file: $VERDICT_FILE"
    python3 -c "
import json, sys
v = json.load(open('$VERDICT_FILE'))
print('verdict :', v.get('verdict'))
print('notes   :', v.get('notes', '')[:400])
findings = v.get('findings', [])
print(f'findings: {len(findings)}')
for i, f in enumerate(findings, 1):
    print(f'  {i}. {f}')
"
fi

case "$RC" in
    0)
        echo ""
        echo "==[ APPROVED ]=================================================="
        # Record commit + status
        COMMIT=$(git rev-parse HEAD)
        python3 "$SCRIPT_DIR/state_helpers.py" set-phase "$PHASE" approved "$COMMIT"
        exit 0
        ;;
    1)
        echo ""
        echo "==[ REVISE ]====================================================="
        if [[ "$REVIEW_N" -ge 2 ]]; then
            echo "Second REVISE; treating as ABORT per protocol."
            python3 "$SCRIPT_DIR/state_helpers.py" halt "$PHASE" "two_consecutive_revise"
            exit 2
        fi
        python3 "$SCRIPT_DIR/state_helpers.py" set-phase "$PHASE" revise_requested
        exit 1
        ;;
    2)
        echo ""
        echo "==[ ABORT ]======================================================"
        python3 "$SCRIPT_DIR/state_helpers.py" halt "$PHASE" "opus_abort"
        exit 2
        ;;
    78)
        echo "API or input error — see stderr." >&2
        exit 78
        ;;
    *)
        echo "Unexpected exit code: $RC" >&2
        exit 78
        ;;
esac
