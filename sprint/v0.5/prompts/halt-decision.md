# Halt-decision prompt template

Use this template when Sisyphus is uncertain whether to halt. Submit it to Opus via the same review pathway as a phase review, but with `scope: "halt_decision"`.

## Payload

```json
{
  "scope": "halt_decision",
  "phase": N,
  "situation": "<2-4 sentence description of the dilemma>",
  "options": [
    {"label": "proceed_with_<X>", "rationale": "..."},
    {"label": "halt_and_ask", "rationale": "..."},
    {"label": "<other>", "rationale": "..."}
  ],
  "context": {
    "relevant_files": ["..."],
    "recent_test_output": "...",
    "phase_brief_excerpt": "...",
    "what_sisyphus_already_tried": "..."
  }
}
```

## Reviewer instructions

You are deciding whether Sisyphus should halt or proceed. Return:

```json
{
  "decision": "PROCEED_WITH_<X>" | "HALT" | "OTHER",
  "notes": "<2-3 sentence justification>",
  "if_proceed_guardrails": ["..."],
  "if_halt_what_to_write": "<what HALT-phase-N.md should contain>"
}
```

## Use sparingly

This is a $0.10–$0.20 call. Sisyphus should reserve it for genuine architectural ambiguity, not every "should I name this X or Y" question. Naming choices: pick one and move on. API contracts with external services: halt and ask.

## Examples of when to use

- "The upstream sandbox API doesn't have a `cwd` param; I see options A, B, C with different trade-offs. Which?"
- "Phase brief says delete `webapp_builder`, but a test for `wide_research` imports from it. Should I delete both or salvage?"
- "Two consecutive REVISE rounds for the same finding. Should I treat as ABORT or attempt a third round with a different strategy?"

## Examples of when NOT to use

- "Test is failing. Should I fix the test or the code?" — fix what the brief says; if the brief is silent, fix the code.
- "Should this function be `snake_case` or `camelCase`?" — project convention says `snake_case` for Python.
- "Should I add type hints?" — yes, always, for new code.
