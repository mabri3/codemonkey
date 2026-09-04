# Loop 23 Research — Eval Noise Isolation (CYCLE R23)

Date: 2026-09-03 · Method: live search (1 query — pytest monkeypatch docs are
canonical) + the A15 incident evidence (5 env-sensitive tests failed under
sweep interleaving, passed clean).

## Root cause of the A15 class
Sweep probes run LIVE execs concurrently with the suite; env-sensitive tests
(cache telemetry, cost, delegate, golden, 6F4) read Codemonkey env
(CODEMONKEY_*) and the shared ~/.codemonkey store mid-write. Anything that
flips env between tests (sweep exports leaked into the same shell, e.g.
CODEMONKEY_TIMEOUT_SECONDS) perturbs timing/behavior.

## SELECTED
1. **CYCLE 60 — env quarantine for env-sensitive tests**: an autouse
   session-scoped fixture snapshot restore for CODEMONKEY_* vars + a
   `clean_env` extension that scrubs ALL CODEMONKEY_* (not just provider) for
   the 5 sensitive test modules explicitly; sweep gains `--offline` to skip
   live probes when running the suite concurrently.
   verify: unit (≥4 tests: scrub removes aliased vars, restore restores,
   sweep offline flag parses, sensitive-list filter).
