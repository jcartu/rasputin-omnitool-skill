---
name: New tool proposal
about: Propose adding a new tool to the skill
title: "[TOOL] "
labels: tool
---

## Tool name

<!-- snake_case, will appear in manifest.json -->

## Capability

<!-- One sentence: what does this tool do? -->

## Backend

<!-- Library, service, or model that powers this tool -->

## Manifest schema (draft)

```json
{
  "name": "your_tool",
  "description": "...",
  "inputs": {
    "param": {"type": "string", "required": true}
  },
  "outputs": {
    "result": {"type": "object"}
  },
  "errors": ["BACKEND_UNAVAILABLE", "INVALID_INPUT"]
}
```

## Required environment variables

<!-- e.g., RASPUTIN_OMNITOOL_<TOOL>_ENDPOINT -->

## Sandbox/safety considerations

<!-- Network egress? Filesystem write? Subprocess spawn? -->

## Test plan

- [ ] Happy path
- [ ] Each declared error code
- [ ] Concurrent invocation (if applicable)
