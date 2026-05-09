#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

python -c "
from agent import run_goal
import json

result = run_goal('Crawl http://example.com and produce a 1-paragraph markdown summary saved to outputs/.')
print(json.dumps({
    'verdict': result['review'].verdict,
    'artifact_count': len(result['artifacts']),
    'step_count': len(result['trace'].steps),
    'revised': result.get('revised', False),
}, indent=2))
"
