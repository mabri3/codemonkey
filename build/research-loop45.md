# Loop 45 research: the evidence pack + v4.0 closing acceptance (CYCLE R45)

**Date:** 2026-09-05 · **Charter:** `build/loops-38-45-proposal.md` (R45) ·
**Entry condition PENDING:** loops 38–44 closed (shipped, or explicitly
rejected in writing), no open critic finding above LOW.
**Core-design NO** — this loop verifies and packages; it invents no new
powers. (No ask on powers; the acceptance criteria below ARE the handoff
terms for Gate 5.)

**Question** (charter): can a run hand its caller a self-contained,
verifiable account of itself — claims linked to the evidence that supports
them, deterministic parts reproducible without the model — and does the
whole arc survive a closing acceptance?

**Published context, UP FRONT (R-G):** verifiable agent execution is active
standards-track work, not a solved product: tamper-evident audit trails
with anchoring ("Agent Flight Recorder",
https://arxiv.org/pdf/2609.01931), cryptographic binding + reproducibility
verification for tool use (https://arxiv.org/pdf/2603.14332), a
Proof-of-Behavior protocol (IETF draft-dembowski-agentledger), and
witness-style audit records (COGITATOR draft). This loop does NOT implement
those protocols — it builds the repo-scale version (hash-chained journal +
linked evidence) and cites the standards track as the direction, honestly
sized: tamper-evident against casual editing, not against a determined
adversary with write access to the chain file.

## In-repo evidence (this repo, not literature)

- `claims` (`check_claims` / `annotate`, agent claims vs journal records)
  already extracts agent claims; `journal` already records runs; `redact`
  already scrubs secrets; `cost` already ledgers spend. For the *agent-claim*
  half the pack is composition + chaining, not new extraction machinery.
  **91F4 correction (2026-09-04):** this bullet originally read
  "`claims` + `truthpass` already extract agent claims". Two errors.
  (a) `truthpass.py` no longer exists — cycle 81 (`5ea507f`) deleted it under
  R-A the same day this file was written. (b) It never did agent-claim
  extraction: it verified *build-ledger* claims (an acceptance row naming
  `tests/x.py` → the file exists and holds ≥ the claimed test count). So the
  **ledger-verification** half of an evidence pack is NOT composition — it is
  machinery this arc deleted, and loop 45 must either rebuild it or scope the
  pack to agent claims only. That choice is now a cycle-level decision, not
  an assumption.
- The journal is append-only by convention, not by construction — no hash
  chain, no tamper evidence.
- `build/CAPABILITY_REGISTER.md` exists; loop-38..44 rows need
  LOCAL / PUBLISHED / GAP triples (R-G) + costs (R-F), and no UNVALIDATED
  rows may remain.
- THREAT_MODEL.md predates the MCP surface (R43), autonomy budgets (R44),
  and evidence packs (R45) — all three change the security surface.

## Candidates (each: name, why, citations)

### C1 — Evidence pack per run
Claims → linked journal record / command output / diff / test result,
redacted, packaged so another agent can check it without re-running the
model. Why: the artifact the whole arc's "honest completion" promise
cash-outs into; verifiable by the caller, not just the runner.

### C2 — Hash-chained journal
Each journal entry commits to the previous entry's hash. Why: makes the
pack tamper-evident (Flight-Recorder direction, repo-sized:
https://arxiv.org/pdf/2609.01931); a broken chain fails verification
instead of passing silently.

### C3 — Separate-process verification, endpoint off
A pack from a real run VERIFIES in a process with the model endpoint
switched off. Why: proves the deterministic half is actually deterministic
— the charter probe's hardest clause, and the one most likely to catch
smuggled model-dependence.

### C4 — CAPABILITY_REGISTER completion
Every row PROVEN-LIVE, UNIT-ONLY with a stated reason, or DEAD — no
UNVALIDATED; loops 38–44 carry local/published/gap + cost. Why: the
register is the arc's honesty ledger; v4.0 ships with it clean or not at
all.

### C5 — Deletion cycles + closing critic pass
Anything that failed its certificate gets a deletion cycle; a final critic
pass with nothing above LOW open. Why: the entry condition's teeth —
rejection in writing, not quiet abandonment.

### C6 — THREAT_MODEL refresh + v4.0 tag + Gate 5 handoff
MCP surface, autonomy budgets, evidence packs in the threat model; final
BUILD_REPORT; tag v4.0; handoff. Why: closing the arc the way Gate 2
closed the last one — with the paperwork matching the code.

## SELECTED (ranked)

1. **C1 + C2** — pack + chain (the verifiable artifact).
2. **C3** — endpoint-off verification (the teeth).
3. **C4 + C5** — register clean, failures rejected in writing.
4. **C6** — refresh, report, tag, handoff.

## Cost note (R-F, charged against the loop that spends it)

Pack-building is local compute + one real instrumented run; endpoint-off
verification is free by construction. The closing sweep is the
acceptance_sweep.sh runtime.

## ACCEPTANCE (the handoff terms — core-design NO, but Gate 5 decides)

`bash build/acceptance_sweep.sh` → all exit 0, zero BLOCKED;
`uv run pytest -q` → exit 0; `uv run codemonkey --version` matches the tag;
register clean per C4; a real-run pack verifies endpoint-off per C3;
THREAT_MODEL.md refreshed; report committed. Then tag v4.0.
