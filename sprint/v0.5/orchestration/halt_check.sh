#!/usr/bin/env bash
# orchestration/halt_check.sh
#
# Quick health check for the sprint. Returns:
#   0 — healthy, can proceed
#   78 — sprint is halted or budget exceeded; do not start next phase

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Hard-stop override
if [[ "${RASPUTIN_OMNITOOL_SPRINT_HARD_STOP:-0}" == "1" ]]; then
    echo "HALT: RASPUTIN_OMNITOOL_SPRINT_HARD_STOP=1"
    exit 78
fi

STATE=$(python3 "$SCRIPT_DIR/state_helpers.py" read)

# Check budget
SPENT=$(echo "$STATE" | python3 -c "import json,sys; s=json.load(sys.stdin); print(s.get('total_cost_usd', 0.0))")
BUDGET=$(echo "$STATE" | python3 -c "import json,sys; s=json.load(sys.stdin); print(s.get('budget_usd', 25.0))")
OVERRUN=$(python3 -c "print('1' if float('$SPENT') > float('$BUDGET') else '0')")
if [[ "$OVERRUN" == "1" ]]; then
    echo "HALT: budget exceeded — spent \$$SPENT > limit \$$BUDGET"
    exit 78
fi

# Check halt status on any phase
HALTED_PHASES=$(echo "$STATE" | python3 -c "
import json, sys
s = json.load(sys.stdin)
ps = s.get('phase_status', {})
halted = [n for n, v in ps.items() if v.get('status') == 'halted']
print(' '.join(halted))
")
if [[ -n "$HALTED_PHASES" ]]; then
    echo "HALT: phases halted: $HALTED_PHASES"
    exit 78
fi

# Check sprint-wide halt reason
HALT_REASON=$(echo "$STATE" | python3 -c "
import json, sys
s = json.load(sys.stdin)
print(s.get('halt_reason') or '')
")
if [[ -n "$HALT_REASON" ]]; then
    echo "HALT: $HALT_REASON"
    exit 78
fi

# Check anthropic + opencode keys
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    echo "HALT: ANTHROPIC_API_KEY not set"
    exit 78
fi
if [[ -z "${OPENCODE_ZEN_API_KEY:-}${RASPUTIN_OMNITOOL_EXECUTOR_ENDPOINT:-}" ]]; then
    echo "HALT: neither OPENCODE_ZEN_API_KEY nor a local executor endpoint configured"
    exit 78
fi

echo "OK: sprint healthy. spent \$$SPENT / \$$BUDGET."
exit 0
