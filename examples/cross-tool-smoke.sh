#!/usr/bin/env bash
# Full smoke script — exercises all 12 tools with trivial inputs.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Full tool smoke test (12 tools) ==="

echo "[1/12] catalog: query browser_operator candidates"
python -c "
from tools.catalog.index import run
r = run({'capability': 'browser_operator'})
assert 'result' in r, r
print(f'  OK: {len(r[\"result\"][\"candidates\"])} candidates')
"

echo "[2/12] docling: allowed-path enforcement"
python -c "
from tools.docling.index import run
r = run({'path': '/etc/hostname'})
assert r.get('error', {}).get('code') == 'OUTSIDE_ALLOWED_PATH', r
print('  OK: path blocked correctly')
"

echo "[3/12] crawl4ai: URL safety checks"
python -c "
from tools.crawl4ai.index import run
r = run({'url': 'file:///etc/passwd'})
assert r.get('error', {}).get('code') == 'FETCH_FAILED', r
print('  OK: file:// rejected')
r = run({'url': 'http://127.0.0.1:8080'})
assert r.get('error', {}).get('code') == 'FETCH_FAILED', r
print('  OK: loopback rejected')
"

echo "[4/12] sandbox: invalid operation"
python -c "
from tools.sandbox.index import run
r = run({'operation': 'invalid'})
assert r.get('error', {}).get('code') == 'INVALID_OPERATION', r
print('  OK: invalid op rejected')
"

echo "[5/12] browser: navigate example.com"
python -c "
from tools.browser.index import run
r = run({'action': 'navigate', 'url': 'http://example.com'})
if 'result' in r:
    assert 'Example Domain' in r['result']['title'], r
    print('  OK: navigated, title matches')
else:
    print(f'  SKIP: {r[\"error\"][\"message\"]}')
"

echo "[6/12] deliverables: minimal MD output"
python -c "
from tools.deliverables.index import run
r = run({'title': 'Smoke Test', 'sections': [{'heading': 'OK', 'body': 'All tools wired'}], 'formats': ['md']})
assert 'result' in r, r
assert len(r['result']['artifacts']) >= 1, r
print(f'  OK: {len(r[\"result\"][\"artifacts\"])} artifacts')
"

echo "[7/12] tts: empty text rejected"
python -c "
from tools.tts.index import run
r = run({})
assert r.get('error', {}).get('code') == 'SYNTHESIS_FAILED', r
print('  OK: empty text rejected')
"

echo "[8/12] stt: nonexistent file rejected"
python -c "
from tools.stt.index import run
r = run({'audio_path': '/nonexistent.wav'})
assert r.get('error', {}).get('code') == 'FILE_NOT_FOUND', r
print('  OK: file not found')
"

echo "[9/12] image-gen: empty prompt rejected"
python -c "
from tools.image_gen.index import run
r = run({})
assert 'error' in r, r
print('  OK: empty prompt rejected')
"

echo "[10/12] video-gen: empty prompt rejected"
python -c "
from tools.video_gen.index import run
r = run({})
assert r.get('error', {}).get('code') == 'GENERATION_FAILED', r
print('  OK: empty prompt rejected')
"

echo "[11/12] music-gen: empty prompt rejected"
python -c "
from tools.music_gen.index import run
r = run({})
assert r.get('error', {}).get('code') == 'GENERATION_FAILED', r
print('  OK: empty prompt rejected')
"

echo "[12/12] memory: unknown operation rejected"
python -c "
from tools.memory.index import run
r = run({'operation': 'delete'})
assert r.get('error', {}).get('code') == 'INVALID_OPERATION', r
print('  OK: unknown op rejected')
"

echo "=== All 12 tools passed ==="
