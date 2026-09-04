# Loop 20 Research — Structured Tool Inputs (CYCLE R20)

Date: 2026-09-03 · Method: live web search (1 focused query) + the shipped
substrate (SPECS registry with per-tool params; verify_command; self-heal
retries feeding errors back).

## Researched capabilities

### 1. Pre-dispatch argument validation + structured correction
- Sources:
  - https://waxell.ai/blog/ai-agent-tool-call-failures-output-rot — schema
    mismatch is the most dangerous failure class; validate inputs.
  - https://medium.com/@Micheal-Lanham/stop-blaming-the-llm... — feed the
    schema error back as a structured correction prompt.
- Why: the 51F1 fix (native schema) made the WIRE honest; the DISPATCH side
  should enforce a required-keys/typecheck per tool (SPECS already declare
  params) BEFORE execution, returning a machine-readable mismatch to the
  model for the self-heal loop instead of a KeyError.
  **SELECTED (cycle 57).**

### 2. additionalProperties:false tightening
- Source: https://community.n8n.io/t/... — permissive schemas rot.
- Why: fold into 57 — strict mode rejects unknown keys (config-tightened).
  **SELECTED (folded).**

## SELECTED

1. **CYCLE 57 — tool-arg validation gate**: `validate_args(tool, args)` from
   SPECS (required keys, type check, optional strict unknown-key rejection);
   mismatch → tool result `{ok: False, error_class: schema_mismatch, detail}`
   fed into the existing self-heal corrective loop.
   verify: unit (≥6 tests: missing required → schema_mismatch with field
   name, wrong type → mismatch, strict mode unknown keys, valid pass-through,
   mismatch feeds corrective loop (marked), non-strict default).
