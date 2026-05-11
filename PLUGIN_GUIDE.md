# Plugin guide for rasputin-omnitool-skill

To add a new tool, create two files. That's it.

## Quick start

```bash
cd ~/workspace/rasputin-omnitool-skill/tools
mkdir my_tool && cd my_tool
```

## 1. Write the manifest

`manifest.json` declares what your tool does, what it accepts, and what it returns.

```json
{
  "name": "my_tool",
  "version": "0.1.0",
  "description": "Does the thing. Must be at least 5 characters long.",
  "inputs": {
    "input_field": {
      "type": "string",
      "required": true,
      "description": "The thing to process"
    },
    "limit": {
      "type": "integer",
      "required": false,
      "default": 10,
      "minimum": 1,
      "maximum": 100
    }
  },
  "outputs": {
    "result_field": {
      "type": "string",
      "description": "The processed output"
    }
  },
  "errors": ["INVALID_INPUT", "BACKEND_FAILED"]
}
```

**Rules:**
- `name` must match the directory name exactly (snake case, lowercase)
- `version` must be valid semver (`0.1.0`, `1.0.0-beta.1`)
- `description` must be at least 5 characters
- Every error code must be uppercase with underscores (`SOME_ERROR`)
- See `agent/schemas/tool_manifest.schema.json` for the full schema

## 2. Write the implementation

`index.py` is your entry point. It must define a top-level `run(inputs: dict) -> dict`:

```python
def run(inputs: dict) -> dict:
    if not inputs.get("input_field"):
        return {"error": {"code": "INVALID_INPUT", "message": "input_field is required"}}

    # Your logic here
    output = inputs["input_field"].upper()

    return {"result": {"result_field": output}}
```

**Contract:**
- Return `{"result": {...}}` on success
- Return `{"error": {"code": "<CODE>", "message": "..."}}` on failure
- The error code MUST be one of the codes declared in `manifest.json#errors`
- Anything else (helpers, classes) is private to the tool

## 3. Optional: Declare backends

If your tool needs an external service, declare it:

```json
{
  "...": "...",
  "backends": [
    {
      "name": "my_service",
      "health_url": "http://localhost:9999/health",
      "health_timeout_s": 3,
      "required": true
    }
  ]
}
```

The registry probes the health URL at startup. If a required backend is down, your tool is marked unavailable and the planner won't dispatch to it. Non-required backends don't block availability.

## 4. Optional: Compose profile

If your tool needs GPU resources:

```json
{
  "...": "...",
  "requires_compose_profile": "gpu-single"
}
```

Profiles: `cpu`, `gpu-single`, `gpu-multi`. Absent means "no specific profile required."

## 5. Optional: Permissions

If your tool runs subprocesses or accesses unusual paths:

```json
{
  "...": "...",
  "permissions": {
    "filesystem": ["read:/etc/some-config"],
    "network": ["egress:*"],
    "subprocess": ["my-binary"]
  }
}
```

These are advisory in v0.4 (logged but not enforced). Future versions may sandbox.

## 6. Write a test

```python
# tests/test_my_tool.py
from tools.my_tool.index import run

def test_happy_path():
    result = run({"input_field": "hello"})
    assert result["result"]["result_field"] == "HELLO"

def test_missing_input():
    result = run({})
    assert result["error"]["code"] == "INVALID_INPUT"
```

## 7. Regenerate the skill manifest and commit

```bash
cd ~/workspace/rasputin-omnitool-skill
python scripts/regenerate-skill-manifest.py
pytest tests/
git add tools/my_tool/ manifest.json
git commit -m "feat(tools/my_tool): add new tool"
```

CI will verify the regenerated manifest matches what's committed.

## How your tool gets used

The planner's prompt is built from `load_tools()`. Your tool appears in the planner's available-tools list automatically. The planner picks it when the tool's description matches a task it's planning.

The executor calls `run(inputs)` with a dict of inputs. Placeholder substitution (`${T1}`, `${T1.key}`) is handled automatically by the executor — you just read from `inputs`.

## Deferred tools

If a tool isn't ready yet but you want to reserve the name:

```json
{
  "name": "future_tool",
  "version": "0.1.0",
  "description": "Will do something amazing eventually.",
  "inputs": {},
  "outputs": {},
  "errors": ["NOT_READY"],
  "status": "deferred",
  "deferred_reason": "Requires GPU with 96GB VRAM; no live endpoint available."
}
```

Deferred tools show up in discovery but are marked unavailable.

## Common pitfalls

1. **Name mismatch** — `manifest.json` `name` must match the directory name exactly. `tools/my_tool/manifest.json` must have `"name": "my_tool"`.
2. **Missing `run()`** — The registry imports `tools.<name>.index` and looks for a callable `run`. If it's missing, the tool is marked invalid.
3. **Error code mismatch** — Every error you return must be declared in `manifest.json#errors`. Undeclared codes are a contract violation.
4. **Forgetting to regenerate** — After adding or changing a per-tool manifest, run `python scripts/regenerate-skill-manifest.py` and commit the updated `manifest.json`. CI catches if you forget.
5. **Blocking imports** — If `index.py` imports a heavy library at the top level, it slows down discovery. Import lazily inside `run()`.

## Schema reference

Full JSON Schema: `agent/schemas/tool_manifest.schema.json`

Required fields: `name`, `version`, `description`, `inputs`, `outputs`, `errors`

Optional fields: `backends`, `requires_compose_profile`, `permissions`, `max_runtime_s`, `tags`, `status`, `deferred_reason`

## Worked example: build a `tools/echo` tool from scratch

```bash
cd ~/workspace/rasputin-omnitool-skill/tools
mkdir echo && cd echo
```

**manifest.json:**
```json
{
  "name": "echo",
  "version": "0.1.0",
  "description": "Returns the input message unchanged. Useful for testing the plugin system.",
  "inputs": {
    "message": {"type": "string", "required": true, "description": "Message to echo back"}
  },
  "outputs": {
    "message": {"type": "string", "description": "The echoed message"}
  },
  "errors": ["EMPTY_MESSAGE"]
}
```

**index.py:**
```python
def run(inputs: dict) -> dict:
    message = inputs.get("message", "")
    if not message:
        return {"error": {"code": "EMPTY_MESSAGE", "message": "message is required"}}
    return {"result": {"message": message}}
```

**Verify it works:**
```bash
cd ~/workspace/rasputin-omnitool-skill
python -c "
from agent.tool_registry import discover_tools
tools = discover_tools()
echo = tools.get('echo')
if echo:
    print(f'Found: {echo.name} v{echo.version}, available={echo.available}')
    result = echo.run({'message': 'hello'})
    print(f'Result: {result}')
else:
    print('echo not found in discovery')
"
```

Expected output:
```
Found: echo v0.1.0, available=True
Result: {'result': {'message': 'hello'}}
```

**Regenerate and commit:**
```bash
python scripts/regenerate-skill-manifest.py
pytest -q
git add tools/echo/ manifest.json
git commit -m "feat(tools/echo): add echo tool for plugin verification"
```

**Clean up:**
```bash
rm -rf tools/echo
python scripts/regenerate-skill-manifest.py
git add tools/ manifest.json
git commit -m "chore: remove echo example tool"
```
