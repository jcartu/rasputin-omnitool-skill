# PHASE 0 — Truth pass (delete the lies)

**Branch:** `sprint/v0.5-phase0`
**Estimated effort:** 2–3 hours
**Depends on:** main branch at v0.4.0 tag

## Objective

Remove every known-broken or fictitious surface so subsequent phases build on a foundation that doesn't lie. No new features. No new behaviour. Strictly subtractive plus minimal corrective edits.

## Why first

Phases 1–9 add real capability. If we add real capability on top of fake stubs, the planner will route to broken tools and we'll waste review cycles diagnosing fabrications. Truth first; capability after.

## Concrete changes

### 1. Delete or quarantine broken tools

| Tool | Action | Reason |
|---|---|---|
| `tools/webapp_builder/` | DELETE | Calls non-existent `npx @bolt.diy/cli`; bolt.diy is a hosted webapp, not a CLI. |
| `tools/wide_research/` | DELETE | NameError in `_decompose` (line 76, self-referencing `depth_instruction`). Will be replaced by the sub-agent tool in Phase 7. |
| `tools/coding_agent/` | FIX | Replace `--repo PATH` with positional file path args. aider has no `--repo` flag. See Patch 1 below. |
| `tools/mail/` | FIX | Remove unused `body_path` write/unlink in `_send`. See Patch 2. |

Also remove from `manifest.json` the entries for `webapp_builder` and `wide_research`.

### Patch 1 — coding_agent

In `tools/coding_agent/index.py`, replace the command builder:

```python
# old:
cmd = [
    "aider",
    "--no-auto-commits",
    "--yes-always",
    "--model", model,
]
if repo_path:
    cmd.extend(["--repo", repo_path])
cmd.extend(["--message", task])

# new:
cmd = [
    "aider",
    "--no-auto-commits",
    "--yes-always",
    "--model", model,
    "--message", task,
]
files = inputs.get("files", [])
if not isinstance(files, list):
    return {"error": {"code": "INVALID_INPUT", "message": "'files' must be a list of paths"}}
cmd.extend(files)
```

Update the manifest at `tools/coding_agent/manifest.json` to remove `repo_path`, add `files: array of string`, and document `cwd` (which is what `repo_path` *should* have been).

### Patch 2 — mail

In `tools/mail/index.py` `_send()`, delete the temp file logic. The `subprocess.run(..., input=body, ...)` already sends body via stdin.

```python
def _send(inputs: dict[str, Any]) -> dict[str, Any]:
    to = inputs.get("to", "")
    subject = inputs.get("subject", "")
    body = inputs.get("body", "")
    if not to:
        return {"error": {"code": "INVALID_INPUT", "message": "Missing 'to' parameter"}}

    cmd = ["himalaya", "send", "--to", to, "--subject", subject]
    result = subprocess.run(cmd, input=body, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        return {"error": {"code": "HIMALAYA_FAILED", "message": f"Himalaya send failed: {result.stderr.strip()}"}}
    return {"result": {"status": "sent", "to": to, "subject": subject}}
```

### 2. Fix pyproject.toml fictions

Remove or replace:
- `voxtral-tts>=0.5` — not on PyPI. Replace with the actual installation path (a GitHub URL via `pip install git+...`) OR mark TTS as backend-only and remove from python deps entirely. **Pick the second:** the TTS tool already health-checks its HTTP backend; no Python package is required.
- `promptfoo>=0.100` — promptfoo is a Node.js package. Remove from `[project.optional-dependencies].dev` and `[project.optional-dependencies].integrations`. Promptfoo is invoked via `npx`; document this in `docs/EVALS.md`.
- `openclaw-skill-sdk>=2026.4.0` — not on PyPI. Remove the line. The integration is via the OpenClaw runtime, not a Python SDK.

Update `description` to say `18 tools` → `16 tools` (post-deletion) and align with `manifest.json` count.

### 3. Fix the docker-compose port collision

`docker-compose.yml`: sandbox holds `8080`, SearXNG mapped to `8888:8080`. But `tools/web_search/index.py` defaults to `http://localhost:8080`. Two fixes:

- Change SearXNG to host port `8889` (8888 is also used by sandbox internal — avoid).
- Set the default in `tools/web_search/index.py` to `http://localhost:8889` AND export `RASPUTIN_OMNITOOL_SEARXNG_URL=http://localhost:8889` in `examples/start-sandbox.sh`.

Document the change in `docs/COMPOSE.md`.

### 4. Remove the personal-path leak

In `surfaces/open-webui/rasputin_function.py`, the default for `rasputin_repo_path` valve is `/home/josh/workspace/rasputin-omnitool-skill`. Change to `""` (empty) with a docstring note that the user must set it via the Valves UI.

### 5. Remove fabricated GHCR images from docker-compose (pin to actual sources)

| Image | Action |
|---|---|
| `ghcr.io/agent-infra/sandbox:latest` | Replace with the project's real image; if none, drop the service and add a README note that users run sandbox from source. |
| `ghcr.io/wan-video/wan-2.1-server:latest` | Drop. Wan 2.1 has no published server image. Phase out of compose; document a manual run if anyone needs `video_gen`. |
| `ghcr.io/musicgen/musicgen-server:latest` | Drop. Same reasoning. |
| `langfuse/langfuse:2` | Pin to the documented `langfuse/langfuse:3` compose stack (which requires Redis + MinIO + ClickHouse + Postgres). Either fold in the full Langfuse 3 stack OR drop Langfuse from compose and document deploying it separately. **Pick the second.** Reduces surface area; users running Langfuse should follow upstream docs. |

After this, compose ships: `sandbox` (if you can find a real image), `searxng`, `comfyui` (`gpu-single`, `gpu-multi`). Three services maximum.

### 6. Truthful manifest

After the deletes, the manifest's tool count must be 14:
`browser, catalog, coding_agent, crawl4ai, deliverables, docling, image_gen, mail, memory, music_gen, sandbox, slides, stt, tts, video_gen, web_search`

(16, after re-counting. The point is: the count matches reality.)

### 7. Update README + SKILL.md tool tables

Bring the tool tables and counts in line with the deleted set.

## Files to change

```
M  manifest.json                     # remove webapp_builder, wide_research
D  tools/webapp_builder/             # whole dir
D  tools/wide_research/              # whole dir
M  tools/coding_agent/index.py       # fix aider call
M  tools/coding_agent/manifest.json
M  tools/mail/index.py               # remove dead temp file
M  tools/web_search/index.py         # change default port
M  pyproject.toml                    # remove fake deps
M  docker-compose.yml                # drop fictitious images + fix ports
M  examples/start-sandbox.sh         # export corrected SearXNG URL
M  surfaces/open-webui/rasputin_function.py  # remove /home/josh default
M  README.md                         # tool table
M  SKILL.md                          # tool table
D  tests/test_open_webui_plugin.py   # only if it tests the broken default
M  tests/test_capability_tools.py    # remove wide_research, webapp_builder tests
```

## Acceptance criteria

- `pytest -v` → all green (test count will drop; that's expected because removed tools = removed tests).
- `ruff check .` → no errors in any file Phase 0 touched.
- `python -c "import json; m=json.load(open('manifest.json')); print(len(m['tools']))"` → matches the count claimed in README and SKILL.md.
- `pip install -e .` succeeds in a fresh venv (no fake deps to fail on).
- `docker compose --profile cpu config` produces a valid compose file with all referenced images pullable (test with `docker compose --profile cpu pull`).
- `grep -r '/home/josh' .` → no matches.
- `grep -rn 'wide_research\|webapp_builder' tools/ tests/ manifest.json` → no matches.

## Self-verification commands

```bash
pytest -v 2>&1 | tee sprint/v0.5/phase-0-pytest.log
ruff check . 2>&1 | tee sprint/v0.5/phase-0-ruff.log
python -c "import json; m=json.load(open('manifest.json')); print(f'tools: {len(m[\"tools\"])}')"
pip install -e . --dry-run 2>&1 | tail -20
grep -r '/home/josh\|wide_research\|webapp_builder' --include='*.py' --include='*.json' --include='*.md' . | grep -v 'sprint/v0.5/' | grep -v '\.git' | grep -v runlog/  # expect empty
docker compose --profile cpu config > /dev/null && echo "compose: OK"
```

## Phase evidence — write to `sprint/v0.5/phase-0-evidence.md`

Template in `rubrics/per-phase-rubric.md`. At minimum:

- Files touched (output of `git diff --stat main..HEAD`)
- Test results (pytest summary line)
- Lint results
- Manifest tool count
- Confirmation that all `grep` checks return empty
- Compose validation output

## Halt conditions specific to Phase 0

- If deleting `wide_research` or `webapp_builder` breaks tests that test *other* tools (cross-coupling), STOP. Document the coupling in the halt file; do not band-aid it.
- If a "real image" for `ghcr.io/agent-infra/sandbox` cannot be located, drop the service from compose and write a `docs/SANDBOX-SETUP.md` describing manual run. Do not invent another image name.

## Out of scope

- New features.
- Refactoring the executor (Phase 2).
- Touching `agent/` Python except for trivial fix-ups to keep tests green after tool deletions.
- Performance work.
- Documentation prettification beyond truthfulness.
