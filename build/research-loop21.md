# Loop 21 Research — Run Digest (CYCLE R21)

Date: 2026-09-03 · Method: live search (1 query; thin results by design —
this loop builds from the shipped substrate, no new machinery needed).

## Finding

An operator today must read the journal, sessions list, cost ledger and
eval state SEPARATELY (status shows totals only). A **run digest** —
`codemonkey digest <thread>` — turns one thread's journal + session meta +
tool trace into a plain-text narrative report: goal, tools used (with
commands), failures by class, files touched, tokens, verdicts
(model_unload_fallback / schema_mismatch / unverified_claim / route swaps).

Sources are thin because this is composition, not research: every input
already ships (journal forensics 33, cost 26, sessions 15).

## SELECTED

1. **CYCLE 58 — `codemonkey digest <thread>`**: markdown digest from
   journal(thread) + sessions meta + eval/journal classes: header (goal
   from session first_prompt, provider/model), tool-use table (counts +
   notable commands), failures section (class × 1-line detail), budget
   (tokens in/out), route/verify_claims flags.
   verify: unit (≥6 tests: header fields, tool counts, failure section,
   route fallback rendering, empty-thread tolerance, --json shape).
