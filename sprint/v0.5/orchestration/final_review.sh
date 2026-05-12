#!/usr/bin/env bash
# orchestration/final_review.sh
#
# Runs the full sprint acceptance suite, packages evidence, and submits
# to Opus for final review. On APPROVE, tags v0.5.0. On REVISE, allows
# one revise round. On ABORT, halts.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! bash "$SCRIPT_DIR/halt_check.sh" >/dev/null 2>&1 ; then
    echo "halt_check failed; cannot run final review" >&2
    exit 78
fi

echo "==[ FINAL REVIEW — sprint v0.5 ]======================================="

# ---- 1. Ensure prior phases approved (or deferred per rubric amendment) ----
# Phases with status=deferred are allowed if a rubric amendment has scope-cut
# them to a later sprint. See sprint/v0.5/rubrics/final-rubric.md amendment block.
for N in 0 1 2 3 4 5 6 7 8; do
    STATUS=$(python3 -c "import json; s=json.load(open('sprint/v0.5/state.json')); print(s.get('phase_status',{}).get('$N',{}).get('status','missing'))")
    if [[ "$STATUS" == "approved" ]]; then
        continue
    elif [[ "$STATUS" == "deferred" ]]; then
        echo "NOTE: phase $N deferred (scope-cut per rubric amendment)."
        continue
    else
        echo "FATAL: phase $N not approved or deferred (status=$STATUS); cannot run final review." >&2
        exit 2
    fi
done

# ---- 2. Lint ----
echo ""
echo "--[ lint ]--"
ruff check . 2>&1 | tee sprint/v0.5/final-ruff.log
RUFF_RC=${PIPESTATUS[0]}

# ---- 3. Full unit suite ----
echo ""
echo "--[ pytest ]--"
pytest -v 2>&1 | tee sprint/v0.5/final-unit.log
PYTEST_RC=${PIPESTATUS[0]}

# ---- 4. e2e_smoke ----
echo ""
echo "--[ e2e smoke ]--"
if [[ -f tests/e2e_smoke.py ]]; then
    pytest -v tests/e2e_smoke.py 2>&1 | tee sprint/v0.5/final-e2e.log
    E2E_RC=${PIPESTATUS[0]}
else
    echo "tests/e2e_smoke.py missing"
    E2E_RC=1
fi

# ---- 5. Golden goals ----
# IMPORTANT: golden goals are inherently flaky (LLM non-determinism + external services).
# Non-zero RC must NOT abort the script via set -e — we want to forward results to Opus.
# Also: never clobber a committed canonical final-golden.log. If it exists in HEAD,
# write this run to a timestamped sibling file instead.
echo ""
echo "--[ golden goals ]--"
GOLDEN_LOG="sprint/v0.5/final-golden.log"
if git ls-files --error-unmatch "$GOLDEN_LOG" >/dev/null 2>&1; then
    GOLDEN_LOG="sprint/v0.5/final-golden-rerun-$(date -u +%Y%m%dT%H%M%SZ).log"
    echo "(canonical final-golden.log already committed; writing this run to $GOLDEN_LOG)"
fi
if [[ -f sprint/v0.5/orchestration/run_golden_goals.py ]]; then
    set +e
    python3 sprint/v0.5/orchestration/run_golden_goals.py 2>&1 | tee "$GOLDEN_LOG"
    GOLDEN_RC=${PIPESTATUS[0]}
    set -e
else
    echo "run_golden_goals.py missing"
    GOLDEN_RC=1
fi

# ---- 6. Compose final-evidence.md if Sisyphus hasn't already ----
EVIDENCE="sprint/v0.5/final-evidence.md"
if [[ ! -f "$EVIDENCE" ]]; then
    echo "FATAL: $EVIDENCE missing — Sisyphus must write it before final review." >&2
    echo "       See rubrics/final-rubric.md for the template." >&2
    exit 2
fi

# ---- 7. Sanity gate before paying for the review ----
if [[ "$PYTEST_RC" -ne 0 || "$RUFF_RC" -ne 0 ]]; then
    echo "FATAL: lint or unit tests failed; aborting final review (no Opus call)." >&2
    exit 2
fi
echo ""
echo "lint=$RUFF_RC  pytest=$PYTEST_RC  e2e=$E2E_RC  golden=$GOLDEN_RC"
echo ""

# ---- 8. Submit to Opus ----
echo "--[ Opus final review ]--"
set +e
python3 "$SCRIPT_DIR/opus_review.py" --scope final --phase 9
RC=$?
set -e

VERDICT_FILE="sprint/v0.5/review-final.json"
if [[ -f "$VERDICT_FILE" ]]; then
    python3 -c "
import json
v = json.load(open('$VERDICT_FILE'))
print('FINAL VERDICT:', v.get('verdict'))
print('Notes:', v.get('notes', '')[:600])
for f in v.get('findings', []):
    print('  -', f)
"
fi

case "$RC" in
    0)
        echo ""
        echo "==[ APPROVED — tagging v0.5.0 ]================================="
        git checkout release/v0.5.0
        git tag -a v0.5.0 -m "Sprint v0.5: first working release"
        git push origin v0.5.0 || echo "(push failed; tag exists locally)"
        python3 - <<'EOF'
import sys
sys.path.insert(0, "sprint/v0.5/orchestration")
from state_helpers import update_state, set_phase_status
from datetime import datetime, timezone
update_state(
    current_phase=10,
    sprint_complete=True,
    completed_at=datetime.now(timezone.utc).isoformat(),
    released_tag="v0.5.0",
)
set_phase_status(9, status="approved")
EOF
        exit 0
        ;;
    1)
        echo ""
        echo "==[ REVISE — address findings and re-run final_review.sh ]======"
        exit 1
        ;;
    2)
        echo ""
        echo "==[ ABORT — sprint cannot complete ]============================"
        HALT="sprint/v0.5/HALT-final.md"
        if [[ ! -f "$HALT" ]]; then
            cat > "$HALT" <<MD
# HALT final review

Opus returned ABORT on final review. See:
- sprint/v0.5/review-final.json
- sprint/v0.5/final-evidence.md

DO NOT tag v0.5.0. Wait for Joshua.
MD
        fi
        exit 78
        ;;
    *)
        echo "Unexpected review exit code: $RC" >&2
        exit 78
        ;;
esac
