# Loop 26 Research — Verify-Gate Defaults + Review Auto-Attach (CYCLE R26)

Date: 2026-09-03 · Method: carried — the fizzbuzz overclaim (live, loop-17
entry evidence) showed fixes aren't verified unless the operator configures
verify_command.

## SELECTED
1. **CYCLE 63 — verify_command auto-proposal**: when a run's final tool set
   includes pytest-invoking shell commands and no verify_command is
   configured, exec prints a one-line suggestion (not silently configured):
   "verify gate available: verify_command: python -m pytest -q". Suggestion
   also persisted to the session meta.
   verify: unit (≥4 tests: pytest-usage detected → suggestion emitted,
   no-pytest → no suggestion, preconfigured → silent, meta persisted).

## NOT SELECTED
- Auto-enabling the gate by default: changes run semantics silently; the
  suggestion keeps the operator in charge (governance precedent from loop 16).
