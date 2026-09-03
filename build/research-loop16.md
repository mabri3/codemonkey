# Loop 16 Research — Hardening, Release Readiness, v1.0 (CYCLE R16)

Date: 2026-09-03 · Method: live web search (2 focused queries) + the shipped
substrate audit.

**Entry condition:** Loops 11–15 closed (all shipped); critic-loop8 findings
fixed and verified; the live-LLM criteria were re-verified in loops 4–5 sweeps
when the home server was healthy (currently flapping — recorded honestly; the
v1.0 tag ships as **1.0.0-rc1 confirmed** with live evidence from earlier
sweeps, per the honest-recording policy; final live re-sweep re-runs when the
endpoint returns).

**Core-design flag (charter): process-level containment redefines sandbox
semantics.** Blanket user authorization covers loops 11–16; the flag is
resolved by NOT changing sandbox level semantics — see finding 1.

## Findings & decisions

### 1. Process-level containment (macOS sandbox-exec / Linux bwrap)
- Sources:
  - https://github.com/apple/containerization/issues/737 — `sandbox-exec` is
    deprecated with no App-Store-independent replacement timeline.
  - https://www.infralovers.com/blog/2026-02-15-sandboxing-claude-code-macos/ —
    practical seatbelt profiles still work but are deprecated.
  - https://tekai.dev/references/2026-04-02-zerobox — third-party cross-platform
    process sandboxing exists but adds a dependency.
- Decision: **NOT SELECTED for v1.0.** sandbox-exec is deprecated with no
  stable replacement; bubblewrap is Linux-only; a third-party binary adds a
  supply-chain dependency to the exact layer we're hardening. The documented
  cwd-escape lexical limitation stays documented (spec), the workdir-check
  guard remains the enforcement, and the THREAT MODEL (cycle 49) states
  plainly what the sandbox does not promise. **Deferred with a written
  rationale** — this satisfies the core-design stop-and-ask by taking the
  documented, non-semantics-changing option.

### 2. Secret redaction across stores — audit + hardening
- Sources: carried (R14 failover writes route records; journal args are
  hashed; sessions store prompts/results which may embed env-derived text).
- Audit needed: journal (hashed args ✅), checkpoints (file contents — by
  design, no secrets unless the user writes them), eval results (stdout
  excerpts — may embed), sessions (prompts — may embed). **SELECTED (cycle
  49): a redaction pass on eval results + journal `output` fields using the
  config's api_key values as needles.**

### 3. Dependency/supply-chain hygiene
- Sources:
  - https://docs.astral.sh/uv/concepts/projects/sync/ — uv.lock reproducibility.
  - https://astral.sh/blog/uv-audit — `uv audit`-style vulnerability checking.
- Audit: uv.lock committed? pyproject pinned? **SELECTED (cycle 49): verify
  lockfile committed + `uv sync --locked` green + record the dependency tree
  hash in the release record.**

### 4. Tagged release + upgrade/rollback story
- v1.0.0-rc1 already tagged (loop10-final). **SELECTED (cycle 49): v1.0.0 tag
  after the closing sweep, CHANGELOG updated, rollback = previous tag.**

### 5. Threat model document
- **SELECTED (cycle 49): THREAT_MODEL.md** — what the sandbox promises
  (workdir-write containment, lexical checks, approval gates, permissions
  rules, checkpoints) and what it does NOT (post-fix cwd-escape class,
  process-level containment absent, secrets-in-files by design).

## SELECTED (loop 16 build list)

1. **CYCLE 49 — hardening + release record**: secret redaction pass (eval
   stdout excerpts + journal output fields against configured API keys);
   supply-chain audit (uv.lock committed, `uv sync --locked` green, dep-tree
   hash recorded); THREAT_MODEL.md.
   verify: unit (≥6 tests: redaction of key-shaped strings in eval/journal
   stores, redaction no-op when keys absent, lockfile check, threat-model
   doc exists with required sections); suite green.
2. **CYCLE 50 — closing acceptance v1.0.0**: full A1–A20 sweep + all-loop
   criteria table + no-BLOCKED-if-endpoint-live rule, final report, v1.0.0
   tag, Gate 2 handoff.
   verify: sweep green (honest environment exceptions recorded); suite green;
   v1.0.0 tagged; report committed.
