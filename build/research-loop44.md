# Loop 44 research: trustworthy autonomy budgets (CYCLE R44)

**Date:** 2026-09-05 · **Charter:** `build/loops-38-45-proposal.md` (R44) ·
**Entry condition PENDING:** R41 must CLOSE first (blast radius needs a
change plan to bound — R41 is researched, not yet built; loop44 cycles are
planned but start only after loop41-final).
**Core-design YES:** this defines what unattended operation *is* —
**R44 ENDS BY ASKING.**

**Question** (charter): the gap between "useful for ten minutes with a human
watching" and "useful overnight" is not capability — it is *stopping*.
Current guardrails are pre-execution (sandbox, approvals, rules). What
runtime contract lets a run be left alone: a declared budget in tokens,
wall-clock, turns, cost and blast radius, enforced by the runtime, that
halts and reports rather than degrading?

**Published context, UP FRONT (R-G):** runtime behavioral contracts as
formal objects with enforcement are current work, not settled practice
("Agent Behavioral Contracts: Formal Specification and Runtime …",
https://arxiv.org/html/2602.22302v1; "Bounded Autonomy: Behavioral
Specification Languages …", https://www.authorea.com/doi/10.22541/au.177083908.89981049).
The oversight side is the binding constraint: human oversight fails first
in agent governance (https://nhimg.org/articles/human-oversight-fails-first-in-ai-agent-governance/),
and HITL design guidance treats reviewer attention as finite
(https://galileo.ai/blog/human-in-the-loop-agent-oversight). So the honest
framing: budgets bound the machine; batching protects the human; neither is
solved by asking more often. No local numbers exist yet — loop-44 probes
create them.

## In-repo evidence (this repo, not literature)

- `cost` ledger and `budget` calculator exist; NOTHING enforces them
  mid-run. A budget today is a report, not a limit.
- Approvals are per-call (`--approval`); no queue, no batching, no ranking
  — oversight fatigue is unmodeled.
- Loop-34 self-authored rules can propose anything, including wider latitude
  — no invariant stops a rule from raising its own budget.
- `jobs` persists enough to resume; halting honestly (report + resume) is
  composition, not new machinery — same pattern as loop 42's use of `jobs`.

## Candidates (each: name, why, citations)

### C1 — Declared budget contract at run start
Tokens, wall-clock, turns, cost, blast radius (files touched, directories
written, commands run) — one object, stated before the first turn. Why:
unenforceable-by-default is how runs degrade; declaration makes halting a
contract event, not a crash. (Behavioral-contracts framing:
https://arxiv.org/html/2602.22302v1.)

### C2 — Runtime enforcement with a distinct exit
The runtime checks C1 mid-run; breach halts, exits distinct (new code, not
a reuse of 3), writes a resumable job file, leaves the workspace
checkpointed. Why: the charter probe as written — halt, report, resume.

### C3 — Blast-radius limits (needs R41)
Files-touched / directories-written caps, measurable in advance off the
loop-41 change plan. Why: the limit that stops "suddenly touches 200
files"; the reason loop44 waits on loop41. Bounded-autonomy spirit:
https://www.authorea.com/doi/10.22541/au.177083908.89981049.

### C4 — Approval batching + ranking
Batch what needs a human, rank by irreversibility, ask once per batch —
instead of per-call interrupts. Why: a queue that fatigues its human is a
rubber stamp (oversight-fails-first); batching is the countermeasure, with
the batch itself auditable in the journal.

### C5 — Self-authored rules can never raise a budget
Invariant, probed: a loop-34 rule proposing a wider budget is rejected,
and the rejection is recorded. Why: the agent must not be able to vote
itself more latitude; this is the probe that makes the invariant real.

### C6 — Honest halting: report + resume
A stopped run reports what it did, what it did not, and how to resume —
via `jobs`. Why: halting that loses state teaches operators to raise
budgets instead of trusting them.

## SELECTED (ranked)

1. **C1 + C2** — declare, enforce, distinct exit, resumable halt.
2. **C5** — the invariant probe (small, load-bearing).
3. **C4** — batching against oversight fatigue.
4. **C3** — after R41 closes.
5. **C6** — throughout: every halt probe asserts resumability.

## Cost note (R-F, charged against the loop that spends it)

Enforcement checks are negligible compute; the cost of this loop is halted
runs that spent budget without finishing — reported as budget-consumed per
probe, honestly, not hidden.

## ASK (R44 ends by asking — core-design YES)

1. Authorize runtime budget enforcement with a new distinct exit code (C1+C2)?
2. Authorize approval batching (per-call interrupts replaced by ranked
   batches, C4)?
3. Confirm the invariant: no self-authored rule may ever raise a budget
   (C5), with rejections recorded?
4. Confirm loop44 starts only after loop41-final (C3 dependency)?
