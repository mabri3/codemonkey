# Proposed forward loops 11–16 — research charters (NOT AUTHORIZED)

Date: 2026-09-03. Author: critic-gate review + roadmap pass requested by the
user (`build/critic-loop8.md` was produced by the same pass; its seven fix
cycles are shipped and green at `c91808d`).

Same shape as `build/loops-5-10-proposal.md`: each loop opens with a research
cycle (`CYCLE R<N>`) that must do live web search with real citations, ≥5
candidates and a ranked `SELECTED` section in `build/research-loop<N>.md`, and
only then appends `loop<N>:` build cycles to `build/plan.md` with literal
verify probes. **Nothing here selects a capability.** A charter names the
question a loop must research, the entry condition that makes the loop worth
opening, and the exit artifact. AGENTS.md §3 forbids silently expanding scope,
so the seeds below are candidates for the research cycle to confirm, re-rank,
or reject — never a pre-approved build list.

## Where the machine actually is (the basis for this arc)

- **Shipped:** loops 1–8 plus the 2026-09-03 critic gate. 360 unit tests.
  Measurement exists (eval harness, golden suite + baseline, cost ledger,
  cache telemetry, strategy matrix); context engineering exists (repo map with
  relevance ranking, compaction bake-off, spill, slimming); recovery exists
  (journal, idempotent replay, forensics CLI, per-call checkpoints, undo).
- **Open, already authorized:** loop 9 build cycles 36–38 (rule-based
  permissions, `delegate`, `delegate_batch`) and loop 10 (interop,
  distribution, closing acceptance). This proposal assumes they land; every
  entry condition below is written so a skipped loop is visible rather than
  silently assumed.
- **Standing gaps this arc inherits:** live-LLM criteria need a re-run before
  Gate 2 (home llama.cpp wedged); mid-turn crash *resume* was deferred in
  loop 7 with the journal named as its prerequisite; model routing was
  deferred in R8; `update_plan` state does not survive a run; the streaming
  partial-response limitation from cycle 23 is still open.
- **Gate 2 (final user acceptance) is still open.** Loops 6–10 hold a blanket
  authorization; **loops 11–16 do not.** They stay proposals until the user
  says otherwise.

## The arc

| Loop | Theme | Entry condition | Exit artifact |
|---|---|---|---|
| 11 | Delegation that measurably pays | Loop 9 shipped `delegate`/`delegate_batch`; loop 5 can score it | Roles (implementer/critic/verifier) kept only where the harness shows a win at fixed cost |
| 12 | Long-horizon work across runs | Delegation is stable; single runs already recover | Durable task state + true mid-turn resume: a week-long job survives restarts |
| 13 | Learning from the run history | Journal + eval + cost data exist in volume | The agent's own history changes its next run — measurably, or the idea is closed |
| 14 | Heterogeneous models and routing | A scoring harness plus ≥2 usable providers | Task-class routing and provider failover, adopted only on measured separation |
| 15 | Operator surface and observability | The agent is trusted to run long and alone | A run is legible while it runs and afterwards: diffs before apply, timeline, artifact browsing |
| 16 | Hardening, release readiness, v1.0 acceptance | Loops 11–15 closed; no open critic finding above LOW | Process-level containment, supply-chain hygiene, a tagged release, closing acceptance |

The ordering is a dependency chain, not a preference. Loop 12 cannot claim
long-horizon reliability without loop 11's delegation being stable; loop 13 has
nothing to learn from without loops 11–12 producing history; loop 14's routing
claims are unfalsifiable without loop 5's harness; loop 16's release claim is
worthless if 11–15 left open findings.

---

## CYCLE R11 — Loop 11: delegation that measurably pays

**Question.** Loop 9 gives the agent `delegate` and `delegate_batch` — a
mechanism. Mechanisms are not wins: cycle 22's convention is that no claim is
made if the numbers do not separate. Which *roles* for a delegated context
(independent implementer, adversarial critic, verifier that only runs the
verify command, retrieval scout) raise the golden-suite pass rate at a fixed
token budget on a 27B-class local model, and which are pure overhead?

**Seeds.** Reviewer/critic subagents scored against a single-agent baseline;
verifier-only delegation (delegate owns the verify gate, cycle 19); scout
delegation for retrieval so the parent's window stays clean; delegation depth
and fan-out limits taken from measurement, not from the default 2; result
summarization contracts (what a delegate is allowed to return); failure
isolation — a delegate that dies must not poison the parent's journal thread.

**Entry condition.** Loop 9 shipped `delegate`/`delegate_batch` and loop 5's
harness can score two configurations on the same tasks. If delegation did not
ship, R11 records BLOCKED and appends no cycles.

**Core-design flag: PARTIAL** — adding roles on top of the shipped delegate
tool is inside the existing architecture; *concurrent model turns inside one
thread* is loop architecture and ends by asking (the R8 flag, unchanged).

**Exit.** `build/research-loop11.md` + `loop11:` cycles, each stating its
expected harness delta (pass rate, tokens, wall) inside its verify probe.

---

## CYCLE R12 — Loop 12: long-horizon work across runs

**Question.** Everything the agent knows about a task dies with the run:
`update_plan` renders to the transcript, sessions store messages, the journal
stores intents — but there is no durable representation of "this job, its
steps, what is done, what is next" that a later run can pick up. Loop 7 also
deferred mid-turn resume with the journal named as its prerequisite. What is
the minimum durable task state that lets a multi-day job survive restarts
without a human re-briefing it, and what does honest mid-turn resume require?

**Seeds.** Durable plan/task store (steps, status, evidence) keyed to a thread,
with a CLI to inspect and re-enter it; mid-turn crash resume off the loop-7
journal (replay the intent that was in flight, exactly once); resumable
long-horizon eval tasks in the harness so the claim is testable; compaction
policy for week-long threads (what must survive a summary); "session
continuation" semantics — what a resumed run is allowed to assume; garbage
collection for journals, spills and checkpoints under a long-running job.

**Entry condition.** Loop 11 closed (delegation stable or explicitly rejected)
and the journal is wired into production runs (31F1 — done). Without the
journal, mid-turn resume is guesswork.

**Core-design flag: YES** — durable task state is close to session-state
strategy semantics (the R7 flag). R12 ends by asking before any cycle changes
what a session *is*.

**Exit.** `build/research-loop12.md` + `loop12:` cycles, including a probe
that kills a run mid-turn and shows the resumed run applying the interrupted
mutation exactly once.

---

## CYCLE R13 — Loop 13: learning from the run history

**Question.** After loops 5–12 the agent will hold a large private corpus about
itself: journal outcomes with failure classes, eval results and baselines, cost
ledgers, checkpoints, session transcripts. Today none of it changes the next
run — `memory` is an append-only file of curated facts. Does using that history
(failure-mode recall, tool-choice priors, retrieval of a past solution for a
similar task) measurably improve the harness, or is it a plausible idea that
does not survive measurement on a small local model?

**Seeds.** Failure-mode memory keyed by error class (loop 7's taxonomy) — "this
edit shape failed here before"; retrieval over past sessions/journals scoped to
the current repo; tool-choice priors derived from journal success rates; memory
curation/decay (the file grows forever today); an explicit anti-goal — no
silent behavior change without a probe that shows the delta; privacy posture
for a cross-repo history store.

**Entry condition.** ≥2 loops of journal + eval history exist in volume, and
loop 5's harness can separate configurations. R13 must be willing to close the
theme: if the deltas do not separate, the exit artifact is a documented "no",
not a shipped feature.

**Core-design flag: PARTIAL** — a new memory implementation is inside the
strategy registry; a cross-repo history store is not, and ends by asking.

**Exit.** `build/research-loop13.md` + `loop13:` cycles, or a documented
rejection with the measurements that killed it.

---

## CYCLE R14 — Loop 14: heterogeneous models and routing

**Question.** R8 deferred model routing. The repo has since lost two full days
of live acceptance to a single wedged endpoint, and the config already carries
multiple providers and protocols. Which task classes (summarize/compact,
propose an edit, review, decide) actually want a different model, does routing
beat a single model on the harness at equal cost, and what does honest failover
look like when the primary endpoint is wedged rather than down?

**Seeds.** Per-task-class model routing driven by config, scored on the golden
suite; a cheap model for compaction/summarization vs the main model for edits;
provider health checks that distinguish "unreachable" from "reachable but
wedged" (the exact failure this repo keeps hitting); declarative failover
chains with the acceptance rule that a fallback is recorded, never silent;
cost-aware routing against the cycle-26 ledger; the streaming partial-response
gap from cycle 23 as a routing/retry concern.

**Entry condition.** ≥2 usable providers reachable at once (otherwise routing
cannot be measured), plus the harness. Without two endpoints R14 records
BLOCKED — this loop must not be built on one live server.

**Core-design flag: YES** — routing changes provider selection, which is core
design. R14 ends by asking.

**Exit.** `build/research-loop14.md` + `loop14:` cycles with raw before/after
tables per task class.

---

## CYCLE R15 — Loop 15: operator surface and observability

**Question.** Everything the agent produces about itself is currently readable
only as files and JSONL: journal, spill, checkpoints, cost ledger, eval
results. A human supervising a long autonomous run cannot see what is happening
without `tail`. What is the smallest operator surface that makes a run legible
while it runs and auditable afterwards — without violating the exec stdout
purity contract that the whole CLI is built on?

**Seeds.** Diff preview before a mutation is applied (and an approval mode that
gates on the diff rather than on the tool name); a run timeline view over the
JSONL event stream; `codemonkey journal`/`undo`/spill browsing unified into one
inspector; a live REPL status line (turn, tokens, cost, budget remaining);
structured run reports for CI consumption; an explicit constraint that every
new surface writes to stderr or its own file — never to exec's stdout.

**Entry condition.** Loop 12's long-horizon runs exist (a surface for
observing 30-second runs is not worth a loop). If runs are still short, R15
narrows to the diff-preview approval mode alone.

**Core-design flag: PARTIAL** — a diff-gated approval mode changes approval
semantics and ends by asking; read-only viewers do not.

**Exit.** `build/research-loop15.md` + `loop15:` cycles, each carrying a probe
that asserts stdout purity is unchanged.

---

## CYCLE R16 — Loop 16: hardening, release readiness, v1.0 acceptance

**Question.** What is genuinely required to call this 1.0 and let it run
unattended on a machine that matters — and what does the closing acceptance
record have to contain for the user's Gate 2 decision to be defensible?

**Seeds.** Process-level containment (macOS `sandbox-exec`, Linux
bubblewrap/seccomp) behind the existing sandbox levels, closing the documented
`shell` cwd-escape gap that lexical containment cannot; secret redaction across
events/sessions/journal/checkpoints if loop 9 did not take it; dependency and
supply-chain hygiene (pinned lockfile audit, `uv` reproducibility); a tagged
versioned release with an upgrade/rollback story; a documented threat model
stating what the sandbox does and does not promise; the closing sweep — A1–A20
plus every loop-2..15 criterion, live, with no BLOCKED rows.

**Entry condition.** Loops 11–15 closed (shipped or explicitly rejected) and no
open critic finding above LOW severity. The live-LLM criteria must be
re-verifiable — i.e. a working endpoint — before this loop can close anything.

**Core-design flag: YES** — process-level containment redefines what the
sandbox levels mean. R16 ends by asking.

**Exit.** `build/research-loop16.md` + `loop16:` cycles ending in
`loop16-final`: the closing acceptance record and the v1.0 tag.

---

## What this proposal deliberately does not do

- **It does not authorize anything.** Loops 6–10 carry a blanket
  authorization; loops 11–16 do not. Every `R<N>` below is appended to
  `build/plan.md` unchecked and stays unchecked until the user says otherwise.
- **It does not pre-rank capabilities.** Each research cycle re-ranks with
  fresh citations when it runs; a seed here may be rejected there.
- **It does not assume its own loops succeed.** Three charters (11, 13, 14)
  can legitimately exit with a documented "no" plus the measurements that
  produced it. A loop that cannot fail is not measuring anything.
- **It does not defer the core-design asks.** Four of the six loops carry a
  YES or PARTIAL core-design flag (12, 14, 15, 16) and end by asking the user
  rather than handing selections to a build tick.
