# Compose stack guide

One-command bring-up of all rasputin-omnitool backends via `docker-compose.yml`.

## Profiles

| Profile | Services | When to use |
|---|---|---|
| `cpu` | sandbox, langfuse (postgres + clickhouse + web), searxng | CPU-only hosts, quick setup, CI |
| `gpu-single` | cpu + comfyui | 1 GPU, image generation workflows |
| `gpu-multi` | gpu-single + wan-worker, musicgen-worker | 2+ GPUs, full multimedia pipeline |

The profile is auto-detected from `nvidia-smi` output:
- 0 GPUs → `cpu`
- 1 GPU → `gpu-single`
- 2+ GPUs → `gpu-multi`

Override with `--profile cpu|gpu-single|gpu-multi`. Skip GPU detection with `--skip-gpu-check`.

## Services

### sandbox (all profiles)
Code execution sandbox via `agent-infra/sandbox`. Provides a secure Jupyter environment with REST API.

- **Port:** 8080 (REST), 18200 (Jupyter), 18888 (extra)
- **Volume:** `./outputs:/workspace/outputs` (read-write)
- **Health:** `curl -fsS http://localhost:8080/v1/health`
- **Used by:** `tools/sandbox` (code_execute, jupyter_kernels_list, file_upload, file_download)

### langfuse-postgres (all profiles)
PostgreSQL 15 backing store for Langfuse. Internal only — no host port exposed.

- **Volume:** named `langfuse-pg` (survives `docker compose down`)
- **Health:** `pg_isready -U langfuse`
- **Used by:** langfuse-web (depends_on: service_healthy)

### langfuse-clickhouse (all profiles)
ClickHouse 24 analytics store for Langfuse. Internal only — no host port exposed.

- **Volume:** named `langfuse-ch` (survives `docker compose down`)
- **Health:** `clickhouse-client --query 'SELECT 1'`
- **Used by:** langfuse-web (depends_on: service_healthy)

### langfuse-web (all profiles)
Langfuse v2 self-hosted observability UI.

- **Port:** 3000 (web UI + public API)
- **Health:** `curl -fsS http://localhost:3000/api/public/health`
- **First run:** Schema migration takes 60-90s. Don't restart during migration.
- **Used by:** `agent/observability.py` (PHASE-3+ telemetry, cost tracking)

### searxng (all profiles)
Privacy-respecting metasearch engine aggregating results from multiple engines.

- **Port:** 8888 (mapped from container 8080)
- **Volume:** `./searxng-config:/etc/searxng:rw`
- **Health:** `wget -q --spider http://localhost:8080/healthz`
- **Used by:** `tools/web_search` (PHASE-5)

### comfyui (gpu-single, gpu-multi)
ComfyUI stable diffusion / FLUX image generation.

- **Port:** 8188
- **Volume:** `${COMFYUI_MODELS_DIR:-~/comfyui-models}:/workspace/models`
- **GPU:** 1 device (NVIDIA)
- **Health:** `curl -fsS http://localhost:8188/`
- **Used by:** `tools/image_gen`
- **Note:** Requires models to be downloaded into the models directory first

### wan-worker (gpu-multi only)
Wan 2.1 video generation server.

- **Port:** 8810
- **Volume:** `${WAN_MODELS_DIR:-~/wan-models}:/models`
- **GPU:** 1 device (NVIDIA)
- **Used by:** `tools/video_gen`
- **Note:** Requires dedicated GPU with 96GB VRAM for full quality

### musicgen-worker (gpu-multi only)
MusicGen-Melody audio generation server.

- **Port:** 8811
- **GPU:** 1 device (NVIDIA)
- **Used by:** `tools/music_gen`

## First-run setup

```bash
cd ~/workspace/rasputin-omnitool-skill
./scripts/bootstrap.sh
```

The script will:
1. Auto-detect your profile (cpu/gpu-single/gpu-multi)
2. Check for port collisions (8080, 3000, 8888, etc.)
3. Verify Docker daemon is responsive
4. Create `.env` from `.env.template` if missing
5. Pull all images for the selected profile
6. Start containers with `docker compose --profile X up -d`
7. Wait up to 120s for all healthchecks to pass
8. Run cross-tool smoke test (probes each tool's declared backends)

### Setting up Langfuse (first run only)

After bootstrap completes:
1. Open http://localhost:3000
2. Create an admin account
3. Create a project
4. Navigate to Settings → API Keys
5. Copy the Public Key and Secret Key
6. Add to `.env`:
   ```
   LANGFUSE_PUBLIC_KEY=pk-...
   LANGFUSE_SECRET_KEY=sk-...
   ```

### Dry run

Preview what would happen without doing anything:

```bash
./scripts/bootstrap.sh --dry-run --profile cpu
```

This prints the service list and exits.

## Customization

### Environment variables (`.env`)

| Variable | Default | Description |
|---|---|---|
| `LANGFUSE_NEXTAUTH_SECRET` | `changeme-dev-secret` | NextAuth secret for Langfuse |
| `LANGFUSE_SALT` | `changeme-dev-salt` | Salt for Langfuse password hashing |
| `COMFYUI_MODELS_DIR` | `~/comfyui-models` | Host path for ComfyUI models |
| `WAN_MODELS_DIR` | `~/wan-models` | Host path for Wan models |
| `WAN_IMAGE` | `ghcr.io/wan-video/wan-2.1-server:latest` | Wan container image |
| `MUSICGEN_IMAGE` | `ghcr.io/musicgen/musicgen-server:latest` | MusicGen container image |
| `OPENCODE_ZEN_API_KEY` | *(required)* | OpenCode Zen API key |
| `ANTHROPIC_API_KEY` | *(required)* | Anthropic API key |
| `RASPUTIN_OMNITOOL_MAX_COST_USD` | `0.50` | Cost ceiling per goal |

### Overriding ports

Edit `docker-compose.yml` directly. For example, to move Langfuse to port 3001:

```yaml
langfuse-web:
  ports:
    - "3001:3000"
```

Then update `bootstrap.sh` port collision check to match.

## Tear-down

```bash
# Stop containers, preserve volumes (data survives)
docker compose --profile cpu down

# Stop and delete volumes (loses Langfuse data)
docker compose --profile cpu down -v
```

**Warning:** `down -v` deletes the named volumes (`langfuse-pg`, `langfuse-ch`). This destroys all Langfuse data including projects, traces, and API keys. Only use if you want a clean slate.

## Troubleshooting

### Port conflict

```
[bootstrap] ✗ port 8080 (sandbox) is already in use
[bootstrap] ✗ either stop the process using it, or override the compose file's port mapping
```

Find the process: `ss -tln | grep :8080` or `lsof -i :8080`. Stop it or change the port mapping in `docker-compose.yml`.

### GPU not detected

```
[bootstrap] auto-detected profile: cpu
```

But you have a GPU? Ensure `nvidia-container-toolkit` is installed:

```bash
sudo apt install nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
nvidia-smi  # should show your GPU
```

### Langfuse healthcheck loop

```
[bootstrap] ⚠ still waiting on: langfuse-web
[bootstrap] ⚠ services may need more time to come up; check 'docker compose ps' yourself
```

First run triggers a Postgres schema migration that takes 60-90 seconds. Wait another 60s and check `docker logs rasputin-langfuse-web`. If you see migration output, it's still working.

### ClickHouse crashloop

```bash
docker logs rasputin-langfuse-ch
```

Common causes:
- Low `shm-size` (compose default is usually fine, but some hosts override it)
- Missing `ulimit nofile` (ClickHouse needs high file descriptor limits)
- Insufficient memory (ClickHouse needs ~1GB minimum)

### Image pull fails

```
ERROR: manifest for ghcr.io/agent-infra/sandbox:latest not found
```

Check network connectivity. Some images are large (ComfyUI ~5GB). Retry:

```bash
docker compose --profile cpu pull
```

### Tool shows unavailable after backend is up

The registry probes backends at startup. If you start a backend after the agent loop is running, the tool stays marked unavailable. Restart the agent loop or call `load_tools()` again to re-probe.

## Updating

```bash
# Pull latest images
docker compose --profile cpu pull

# Restart with new images
./scripts/bootstrap.sh
```

## Adding a service (worked example)

Adding a new backend service for a hypothetical `tools/translator` tool:

### 1. Add to docker-compose.yml

```yaml
translator:
  image: ghcr.io/my-org/translator:latest
  container_name: rasputin-translator
  ports:
    - "9090:9090"
  healthcheck:
    test: ["CMD", "curl", "-fsS", "http://localhost:9090/health"]
    interval: 10s
    timeout: 3s
    retries: 5
  profiles: ["cpu", "gpu-single", "gpu-multi"]
```

### 2. Add port to bootstrap.sh collision check

```bash
PORTS=( [8080]=sandbox [3000]=langfuse [8888]=searxng [9090]=translator )
```

### 3. Add backend declaration to tool manifest

```json
{
  "name": "translator",
  "...": "...",
  "backends": [
    {
      "name": "translator_api",
      "health_url": "http://localhost:9090/health",
      "required": true
    }
  ]
}
```

### 4. Regenerate skill manifest

```bash
python scripts/regenerate-skill-manifest.py
```

### 5. Test

```bash
./scripts/bootstrap.sh --profile cpu
# Check translator appears as available in smoke test
```
