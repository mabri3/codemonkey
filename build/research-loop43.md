# Loop 43 research: the caller contract (CYCLE R43)

**Date:** 2026-09-05 · **Charter:** `build/loops-38-45-proposal.md` (R43) ·
**Entry condition FULFILLED:** R38 closed.
**Core-design YES:** a published contract constrains every future loop, and
an MCP surface is a new trust boundary — **R43 ENDS BY ASKING.**

**Question** (charter): `build/intent.md` names the actual users — *other
agents* calling `codemonkey exec` as a subprocess, and CI. Loop 10 deferred
MCP. What must codemonkey expose for another agent to drive it *reliably* —
and is MCP now justified, or is the honest answer still "a clean subprocess
contract"?

**Published context, UP FRONT (R-G):** the 2026 interop split is
MCP-for-tools / A2A-for-delegation / ACP-for-editors, covered by multiple
independent surveys (https://zylos.ai/research/2026-03-26-agent-interoperability-protocols-mcp-a2a-acp-convergence/,
https://appscale.blog/en/blog/mcp-vs-a2a-vs-acp-agent-interop-standards-2026,
https://codex.danielvaughan.com/2026/05/29/agent-to-agent-communication-protocols-a2a-vs-acp-vs-mcp-compared/).
MCP is the default agent↔tool plumbing (charter-stated ~97M monthly SDK
downloads, native vendor support). A2A's "agent card" is the pattern for
machine-readable capability advertisement. None of this says codemonkey
needs MCP — it says the *caller* side has standardized, so our contract
should meet the standard where it is cheap and diverge where it is not.

## In-repo evidence (this repo, not literature)

- The subprocess surface exists and is under-specified: exit codes grew by
  accretion (exit 3 for gave-up, loop 39), the JSONL event schema has no
  version field, `--output-schema` guarantees are unwritten, resumability
  (`jobs`, `resume`) is real but undocumented as a contract.
- A second process has never driven codemonkey using only documentation —
  no conformance suite exists, so "documented" is currently aspirational.
- Loop-10 MCP deferral rationale still holds technically; what changed is
  the ecosystem (callers now speak MCP natively), not the repo.

## Candidates (each: name, why, citations)

### C1 — Exit-code taxonomy, specified
Every exit code codemonkey can produce, what it means, what the caller
should do. Why: the cheapest reliability upgrade; CI callers decide on
exit codes alone.

### C2 — Versioned JSONL event schema
A `v` field on every event, a schema document, and a compatibility rule
(additive minor, breaking major). Why: agents parse streams, not prose; an
unversioned stream is a standing breakage risk. The charter probe (a
deliberate schema change FAILS the conformance suite) is directly this.

### C3 — `--output-schema` guarantees + resumability contract
What the final payload shape is, and what a caller can rely on across
releases for `jobs`/`resume`. Why: closes the loop C1+C2 open — start
contract, stream contract, result contract.

### C4 — Conformance suite a caller can run
Second independent process drives codemonkey end-to-end on documentation
alone; green against the released binary. Why: the deliverable that makes
the contract real rather than aspirational; also the regression net for all
future loops (a loop that breaks the contract fails the suite).

### C5 — MCP: SERVER, not client (recommendation with reasons)
Expose `exec`/`review`/`status` as MCP tools to another agent (server)
versus consuming other servers' tools inside runs (client). Reasons for
server: our callers are agents that already speak MCP — meeting them costs
one narrow surface; client mode would pipe untrusted third-party tool
output into runs that write files, a trust boundary this repo's sandbox
was never designed for. Server first; client explicitly deferred with the
threat model as the reason, not lack of time.

### C6 — Agent-card-style capability advertisement
Machine-readable: what the binary can do, sandbox levels, cost knobs. Why:
A2A's agent-card pattern applied to a subprocess — lets a caller agent
decide before spending.

## SELECTED (ranked)

1. **C1 + C2 + C3** — the subprocess contract, specified end to end.
2. **C4** — conformance suite; the charter probe as written.
3. **C5** — MCP server recommendation, decision in the ask.
4. **C6** — advertisement alongside the server.

## Cost note (R-F, charged against the loop that spends it)

Contract work is mostly specification + suite runtime (short local
probes). An MCP server dependency adds supply-chain surface (recorded in
THREAT_MODEL.md per the loop-45 refresh).

## ASK (R43 ends by asking — core-design YES)

1. Authorize publishing the subprocess contract (C1–C3) as a constraint on
   all future loops (contract-breaking changes fail C4)?
2. MCP decision: authorize SERVER (C5 recommendation)? Explicitly confirm
   CLIENT stays deferred on trust-boundary grounds?
3. Authorize the new trust boundary an MCP server creates (networked tool
   surface into exec-capable runs)?
