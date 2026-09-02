# Proposed forward loops 5–10 — research charters (NOT AUTHORIZED)

Date: 2026-09-02. Author: implementation-review + roadmap pass requested by the
user. This document proposes the **next six loops** in the framework's shape:
each loop opens with a research cycle (`CYCLE R<N>`) that must do live web
search with real citations, ≥5 candidates and a ranked `SELECTED` section
(`build/research-loop<N>.md`), and only then appends `loop<N>:` build cycles to
`build/plan.md`.

Nothing here selects a capability. A charter names the *question a loop must
research*, the *entry condition* that makes the loop worth opening, and the
*exit artifact*. AGENTS.md §3 forbids silently expanding scope, so the
candidates listed are seeds for the research cycle to confirm, re-rank, or
reject — never a pre-approved build list.

## Standing gates

- **Gate 2 (user acceptance of loop 3) is still open.** Loop 4 built anyway
  under direct user instruction; loops 5–10 stay proposals until the user says
  otherwise.
- **Core-design stop-and-ask.** Any loop whose selections touch providers,
  protocol, strategy architecture, or sandbox/approval semantics must end its
  research cycle by asking the user rather than handing cycles to a build tick.
  That flag is marked per charter below.
- **The ordering is a dependency chain, not a preference.** Loop 6 cannot rank
  context strategies without loop 5's measurement; loop 8 cannot claim a
  throughput win without the same; loop 9's unattended-run posture assumes
  loop 7's recovery story. A loop may be skipped, but skipping one makes the
  next one's claims unfalsifiable.

## The arc

| Loop | Theme | Entry condition | Exit artifact |
|---|---|---|---|
| 5 | Measurement + extension points | 4 loops of improvements, zero ability to measure whether any helped | An eval harness that scores a run; per-run cost/token accounting |
| 6 | Context engineering for a small local model | Loop 5 can score a change | Retrieval + compaction chosen by measurement, not intuition |
| 7 | Reliability and recovery | Runs are long, failures are mid-turn | A durable journal; resumable, idempotent recovery |
| 8 | Throughput and cost control | Recovery is safe enough to parallelize | Bounded-concurrency execution with cost guardrails |
| 9 | Governance for unattended runs | The agent is trusted to run alone | Rule-based permissions, redaction, audit trail |
| 10 | Interop, distribution, closing acceptance | The core is stable | MCP/plugin surface (if justified), packaging, final sweep |

---

## CYCLE R5 — Loop 5: measurement + extension points
*(already appended to plan.md by CYCLE R4; charter restated here)*

**Question.** After four loops we still cannot answer "did loop N make the agent
better?" Every claim rests on unit tests plus one-off live probes. What is the
smallest local eval harness that makes a loop's claim falsifiable, and what does
a run cost?

**Seeds (carried forward from R4, to be re-researched with fresh citations):**
local eval harness for the agent itself; token/cost accounting per run and per
turn; hooks + rule-based command permissions; subagents / delegated context
isolation; MCP client.

**Core-design flag: YES** — subagents change loop architecture and
hooks/permissions change sandbox+approval semantics. R5 ends by asking.

**Exit.** `build/research-loop5.md`; `loop5:` cycles appended unchecked.

---

## CYCLE R6 — Loop 6: context engineering, chosen by measurement

**Question.** The repo map (cycles 20–21) ranks by git recency and symbol
density, and compaction is a strategy selected by config. Both were adopted on
reasoning, not evidence. With loop 5's harness available, which retrieval and
which compaction strategy actually score better for a 27B-class local model,
and how much context is the right amount before quality falls?

**Seeds.** Structural/semantic retrieval beyond a symbol index; context-window
telemetry (what fraction of the prefix is ever attended to); compaction
strategy bake-off (summarizing vs sliding-window vs a third candidate) scored on
the harness; "context rot" / lost-in-the-middle effects at small model sizes;
retrieval-vs-agentic-search trade-offs.

**Entry condition.** Loop 5 shipped a harness that can score two configurations
of the same agent against the same tasks. Without it, this loop is opinion.

**Core-design flag: PARTIAL** — adding a strategy implementation is inside the
existing pluggable architecture (no ask); replacing the architecture is not.

**Exit.** `build/research-loop6.md` + `loop6:` cycles, each of which must state
its expected harness delta as part of its verify probe.

---

## CYCLE R7 — Loop 7: reliability and recovery

**Question.** A long headless run that dies mid-turn currently loses the turn:
sessions persist messages, checkpoints snapshot files, but there is no single
journal that says what was attempted, what was applied, and what is safe to
replay. What is the minimum durable record that makes a run resumable at the
point of failure without re-applying a mutation twice?

**Seeds.** Write-ahead journal of tool intents and outcomes; idempotency keys
for mutating tools; crash-resume semantics (resume mid-turn, not just
mid-thread); checkpoint/undo maturity (multi-file, cross-turn); a failure
taxonomy derived from loop 5's harness runs; provider-level partial-response
handling (the streaming retry limitation recorded in cycle 23).

**Entry condition.** None beyond the current code — but its priority ordering
should be set by which failures the loop-5 harness actually produces.

**Core-design flag: NO** for journaling and idempotency; **YES** if it proposes
changing session-state strategy semantics.

**Exit.** `build/research-loop7.md` + `loop7:` cycles.

---

## CYCLE R8 — Loop 8: throughput and cost control

**Question.** Tool calls within a turn already run in a bounded thread pool.
Where else does a headless run waste wall-clock and tokens, and which of those
can be reclaimed without making failures harder to reason about?

**Seeds.** Batched multi-file edits as one intent; provider connection reuse and
streaming budget; prefix-cache hit measurement (does cycle 22's `cache_prompt`
actually pay?); bounded concurrency across independent sub-tasks (depends on
whether loop 5 authorized subagents); per-run token/cost budgets with a hard
stop; queueing for CI use with multiple concurrent `codemonkey exec` calls.

**Entry condition.** Loop 7's recovery story — parallelism multiplies the cost
of an unrecoverable mid-run failure.

**Core-design flag: YES** if it proposes concurrent *model* turns (loop
architecture); NO for transport-level and batching work.

**Exit.** `build/research-loop8.md` + `loop8:` cycles with before/after timing
and token probes recorded raw (the cycle-22 convention: no claim if the numbers
do not separate).

---

## CYCLE R9 — Loop 9: governance for unattended runs

**Question.** The agent is designed to be driven by other agents and by CI, with
`--approval never` and `workspace-write`. Under that posture, `shell` is
all-or-nothing and the JSONL event stream and session store have never been
audited for secret leakage. What does a defensible unattended posture require?

**Seeds.** Rule-based command allow/deny matching (the R4 candidate 7 deferral,
if loop 5 did not already take it); secret redaction across events, sessions,
and checkpoints; an append-only audit trail of executed commands and applied
mutations; process-level sandbox hardening beyond lexical path containment;
network egress policy for `web_fetch`; the `shell` cwd-escape gap documented in
sandbox.py.

**Entry condition.** The agent is actually being run unattended. If it is not,
this loop is premature and should be closed with a note.

**Core-design flag: YES** — this is sandbox and approval semantics by
definition. R9 ends by asking.

**Exit.** `build/research-loop9.md` + `loop9:` cycles.

---

## CYCLE R10 — Loop 10: interop, distribution, closing acceptance

**Question.** What is required to hand this tool to a second user or a second
machine, and is there now a concrete need that an MCP client or plugin surface
would serve?

**Seeds.** MCP client (deferred three times — R10 must either justify it with a
concrete need or close it permanently); a documented extension point for
config-declared tools; packaging and versioned release; `--help`/docs surface
audit against the shipped flag set; a consolidated final acceptance sweep
(A1–A20 plus every loop-2..9 criterion) and a closing BUILD_REPORT.

**Entry condition.** The core loop is stable — no open critic findings above
LOW severity.

**Core-design flag: NO**, with one exception: config-declared external tools
would change the tool registry contract.

**Exit.** `build/research-loop10.md` + `loop10:` cycles, ending in a
`loop10-final` full re-sweep and the run's closing report.

---

## What this proposal deliberately does not do

- It does not rank capabilities across loops. Each `R<N>` re-ranks with fresh
  citations at the time it runs; a candidate seeded here may be rejected there.
- It does not schedule work against Gate 2. Every cycle below is appended
  unchecked and stays unchecked until the user authorizes the loop.
- It does not pre-commit to MCP, subagents, hooks, or concurrency. Those are the
  four items that have survived multiple deferrals precisely because their cost
  is real; three of them are core-design and require the user's word.
