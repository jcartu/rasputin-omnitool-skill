#!/usr/bin/env bash
# Bootstrap rasputin-omnitool-skill compose stack.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# ----- Pretty output --------------------------------------------------------
say()  { printf "[bootstrap] %s\n" "$*"; }
ok()   { printf "[bootstrap] ✓ %s\n" "$*"; }
warn() { printf "[bootstrap] ⚠ %s\n" "$*"; }
fail() { printf "[bootstrap] ✗ %s\n" "$*" >&2; }

# ----- Args -----------------------------------------------------------------
PROFILE=""
DRY_RUN=false
SKIP_GPU_CHECK=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --skip-gpu-check) SKIP_GPU_CHECK=true; shift ;;
    -h|--help)
      echo "Usage: $0 [--profile cpu|gpu-single|gpu-multi] [--dry-run]"
      exit 0
      ;;
    *) fail "unknown arg: $1"; exit 1 ;;
  esac
done

# ----- Detect host capability -----------------------------------------------
detect_profile() {
  if ${SKIP_GPU_CHECK}; then
    echo "cpu"
    return
  fi
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo "cpu"
    return
  fi
  local gpu_count
  gpu_count=$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l)
  if [[ "${gpu_count}" -ge 2 ]]; then
    echo "gpu-multi"
  elif [[ "${gpu_count}" -eq 1 ]]; then
    echo "gpu-single"
  else
    echo "cpu"
  fi
}

if [[ -z "${PROFILE}" ]]; then
  PROFILE=$(detect_profile)
  say "auto-detected profile: ${PROFILE}"
fi

case "${PROFILE}" in
  cpu|gpu-single|gpu-multi) ;;
  *) fail "invalid profile: ${PROFILE}"; exit 1 ;;
esac

# ----- Port collision check -------------------------------------------------
declare -A PORTS
case "${PROFILE}" in
  cpu)
    PORTS=( [8080]=sandbox [3000]=langfuse [8888]=searxng )
    ;;
  gpu-single)
    PORTS=( [8080]=sandbox [3000]=langfuse [8888]=searxng [8188]=comfyui )
    ;;
  gpu-multi)
    PORTS=( [8080]=sandbox [3000]=langfuse [8888]=searxng [8188]=comfyui [8810]=wan [8811]=musicgen )
    ;;
esac

for port in "${!PORTS[@]}"; do
  if ss -tln 2>/dev/null | grep -q ":${port} "; then
    fail "port ${port} (${PORTS[$port]}) is already in use"
    fail "either stop the process using it, or override the compose file's port mapping"
    exit 2
  fi
done
ok "port collisions: none"

# ----- Docker check ---------------------------------------------------------
if ! docker ps >/dev/null 2>&1; then
  fail "docker daemon not responsive"
  exit 3
fi
ok "docker daemon: up"

# ----- .env file check ------------------------------------------------------
if [[ ! -f .env ]]; then
  warn ".env not found. Creating from template..."
  cp .env.template .env
  ok "created .env from template — fill in secrets before running goals"
fi

# ----- Pull / Up ------------------------------------------------------------
if ${DRY_RUN}; then
  say "[dry-run] would pull images for profile ${PROFILE}"
  docker compose --profile "${PROFILE}" config --services
  exit 0
fi

say "pulling images for profile ${PROFILE}..."
docker compose --profile "${PROFILE}" pull

say "starting services..."
docker compose --profile "${PROFILE}" up -d

# ----- Wait for healthchecks ------------------------------------------------
say "waiting for healthchecks (up to 120s)..."
for i in $(seq 1 24); do
  unhealthy=$(docker compose --profile "${PROFILE}" ps --format json 2>/dev/null | \
              python3 -c "
import json, sys
for line in sys.stdin:
    if not line.strip(): continue
    svc = json.loads(line)
    if svc.get('Health') in ('starting', 'unhealthy'):
        print(svc.get('Service'))
" || true)
  if [[ -z "${unhealthy}" ]]; then
    ok "all services healthy"
    break
  fi
  if [[ $i -eq 24 ]]; then
    warn "still waiting on: ${unhealthy}"
    warn "services may need more time to come up; check 'docker compose ps' yourself"
  fi
  sleep 5
done

# ----- Cross-tool smoke -----------------------------------------------------
say "running cross-tool smoke (probes each tool's backend)..."
python3 -c "
from agent.tool_registry import load_tools
tools = load_tools()
print(f'discovered {len(tools)} tools:')
for name, tool in sorted(tools.items()):
    status = 'available' if tool.available else 'unavailable'
    backend_summary = ', '.join(f'{b.name}={\"up\" if b.available else \"down\"}' for b in tool.backend_statuses) or '(no backends)'
    print(f'  {name:20s} {status:12s} {backend_summary}')
" 2>&1 | tee /tmp/bootstrap-smoke.log

# ----- Done -----------------------------------------------------------------
echo ""
echo "============================================================================"
ok "bootstrap complete (profile: ${PROFILE})"
echo "============================================================================"
echo ""
echo "Next steps:"
echo "  - Edit .env if you haven't (fill in API keys)"
echo "  - Open http://localhost:3000 to set up Langfuse project (first run only)"
echo "  - Run a goal: python -c 'from agent import run_goal; print(run_goal(\"hello\"))'"
echo "  - Tear down: docker compose --profile ${PROFILE} down"
echo "  - Wipe volumes too (loses Langfuse data): docker compose --profile ${PROFILE} down -v"
echo ""
