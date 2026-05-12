# Open WebUI Setup

rasputin-omnitool-skill as an Open WebUI Tool. Lets you type goals in chat and get artifacts back.

## Prerequisites

- Open WebUI installed and running (port 3001)
- rasputin-omnitool-skill at `~/workspace/rasputin-omnitool-skill`
- Compose stack up (sandbox, SearXNG, etc.)

## Plugin Install

### Method 1: Admin UI (recommended)

1. Visit `http://localhost:3001/admin/settings/tools`
2. Click "+ Add Tool"
3. Paste the contents of `surfaces/open-webui/rasputin_function.py`
4. Click "Save"
5. Enable the tool for your model

### Method 2: Volume Mount (dev-friendly)

```bash
docker stop open-webui
docker rm open-webui
docker run -d \
  --name open-webui \
  -p 3001:8080 \
  -v open-webui-data:/app/backend/data \
  -v ~/workspace/rasputin-omnitool-skill:/host-rasputin-skill:ro \
  --add-host=host.docker.internal:host-gateway \
  --restart unless-stopped \
  ghcr.io/open-webui/open-webui:main
```

Set `rasputin_repo_path` valve to `/host-rasputin-skill`.

## Configuration

| Valve | Default | Description |
|-------|---------|-------------|
| `max_cost_usd` | 0.50 | Per-goal cost ceiling in USD |
| `show_steps` | true | Stream executor steps to chat |
| `outputs_base_url` | file:///app/backend/data/outputs | Where outputs/ is mounted |
| `rasputin_repo_path` | empty | Path to skill repo; set this in the Valves UI |

## Usage

1. Open a new chat with the model that has the tool enabled
2. Type your goal: `Find OSS sandboxing tools and produce a 3-sentence markdown summary.`
3. Watch status updates: "Planning..." → "Done"
4. Final reply contains verdict, summary, and artifact links

## Streaming Behavior

When `show_steps` is enabled:
- "Planning..." appears when the planner LLM is called
- "Done" appears when the goal completes
- Errors show inline with the exception message

## Artifact Links

Artifacts are written to `outputs/`. The `outputs_base_url` valve controls how they're linked. For local use, `file://` links work in most browsers. For remote access, mount `outputs/` to a static file server.

## Cost Ceiling

Set `max_cost_usd` in the tool's Valves. When hit:
- Goal halts cleanly
- Chat shows "⛔ Goal halted: cost_ceiling_exceeded"
- No Python traceback

## Troubleshooting

- **"Could not load skill"** → Check `rasputin_repo_path` valve
- **Tool doesn't appear** → Check file syntax, check Open WebUI logs
- **Artifacts don't link** → Check `outputs_base_url` valve
- **Tool isn't invoked** → Model may need explicit hint, or model's tool-calling is weak

## Security

The plugin has read access to the user's chat session. Be careful about PII/credentials in goals. The cost ceiling protects against runaway cost.
