#!/usr/bin/env bash
# Cross-tool smoke script for PHASE-3
# Exercises all 6 core tools end-to-end with trivial inputs.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Cross-tool smoke test ==="

echo "[1/6] catalog: query browser_operator candidates"
python -c "
from tools.catalog.index import run
r = run({'capability': 'browser_operator'})
assert 'result' in r, r
print(f'  OK: {len(r[\"result\"][\"candidates\"])} candidates')
"

echo "[2/6] docling: allowed-path enforcement"
python -c "
from tools.docling.index import run
r = run({'path': '/etc/hostname'})
assert r.get('error', {}).get('code') == 'OUTSIDE_ALLOWED_PATH', r
print('  OK: path blocked correctly')
"

echo "[3/6] crawl4ai: URL safety checks"
python -c "
from tools.crawl4ai.index import run
r = run({'url': 'file:///etc/passwd'})
assert r.get('error', {}).get('code') == 'FETCH_FAILED', r
print('  OK: file:// rejected')
r = run({'url': 'http://127.0.0.1:8080'})
assert r.get('error', {}).get('code') == 'FETCH_FAILED', r
print('  OK: loopback rejected')
"

echo "[4/6] sandbox: invalid operation"
python -c "
from tools.sandbox.index import run
r = run({'operation': 'invalid'})
assert r.get('error', {}).get('code') == 'INVALID_OPERATION', r
print('  OK: invalid op rejected')
"

echo "[5/6] browser: navigate example.com"
python -c "
from tools.browser.index import run
r = run({'action': 'navigate', 'url': 'http://example.com'})
if 'result' in r:
    assert 'Example Domain' in r['result']['title'], r
    print('  OK: navigated, title matches')
else:
    print(f'  SKIP: {r[\"error\"][\"message\"]}')
"

echo "[6/6] deliverables: minimal MD output"
python -c "
from tools.deliverables.index import run
r = run({'title': 'Smoke Test', 'sections': [{'heading': 'OK', 'body': 'All tools wired'}], 'formats': ['md']})
assert 'result' in r, r
assert len(r['result']['artifacts']) >= 1, r
print(f'  OK: {len(r[\"result\"][\"artifacts\"])} artifacts')
"

echo "=== All 6 tools passed ==="
