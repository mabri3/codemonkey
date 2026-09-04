# Proposed forward loops 38–45 — the utility arc (NOT AUTHORIZED)

Date: 2026-09-04. Author: forward-planning pass requested by the user after the
post-v3.0.0 closing review (`build/critic-r37.md`), with the brief "items that
can truly 10x the utility of codemonkey".

**Predecessor arcs.** `build/loops-17-27-proposal.md` (the debt arc) and
`build/loops-28-37-proposal.md` (the capability arc). Their §0 handoff
contract, §2 debt ledger and arc rules **R-A … R-G apply unchanged here** and
are not restated. Read both before this file; this one adds two rules and eight
charters.

---

## §0 — The finding this arc is built on

The closing review found something bigger than the five bugs it fixed
(`build/critic-r37.md` F7): **eight of the ten loop-28..36 capability modules
are not imported by any source file.** `graphquery`, `certify`, `branches`,
`bestofn`, `rubrics`, `adaptivemem` and `learnedctx` are correct, documented,
unit-tested — and unreachable from `exec`, from the tool registry, from the
strategy registry and from the eval harness. `tools.SPECS` contains no graph
tool at all, which was loop 28's entire premise.

They are described as shipped capabilities of v3.0.0 in `features.html` and in
the R37 BUILD_REPORT. They are not. Nothing was faked: every loop-28..36 verify
probe was written against the module's *unit tests*, and every one of those
probes passed honestly. The grammar of the probe was the defect.

That reframes what "10x utility" means here. The arc does **not** open by
adding capability number eleven:

> **The largest available multiplier in this repo is not a new technique. It is
> the seven techniques already written, tested and paid for that currently
> multiply real runs by exactly 1.0×.**

So loop 38 is a *reachability* loop with no new features in it, and every later
charter must reach a user- or agent-visible surface before it may be called
done. The measurement machinery (loop 30's certificates, loop 40's tests) is
what tells us which of the seven were worth wiring — some will be deleted, and
R-A ("measure or delete") means deletion is a success, not a retreat.

---

## §A — The eight charters

| Loop | Charter | Why it can actually 10x | Published anchor | Primitive already in the repo |
|---|---|---|---|---|
| 38 | Reachability: wire the orphans, prove them at the entry point | seven built capabilities go from 0× to whatever they are worth; also the only way to find out which are worthless | — (in-repo evidence: `build/critic-r37.md` F7/F8) | `graphquery`, `certify`, `branches`, `bestofn`, `rubrics`, `adaptivemem`, `learnedctx` — all written, all tested |
| 39 | Failure-anchored recovery | failure trajectories run 12–82% longer than successful ones; an agent that *notices* its first unrecoverable step stops burning the budget after it ([Failure as a Process](https://arxiv.org/html/2607.09510v1), [Debugging the Debuggers](https://arxiv.org/pdf/2605.08717), [AgentAtlas](https://arxiv.org/html/2605.20530v1)) | the journal already records typed `error_class` per step; `lessons`, `digest`, `retry`, `checkpoints` |
| 40 | The test loop as the primary control signal | a reproduction test converts "did I fix it" from a model judgment into an exit code — the single biggest lever on a weak endpoint; e-Otter++ reports 63% fail-to-pass on TDD-Bench Verified ([EvoOtter](https://arxiv.org/pdf/2607.02854), [reproduction tests](https://arxiv.org/pdf/2605.04320), [execution-feedback test gen](https://arxiv.org/html/2508.06365)) | the cycle-19 verify gate, `verifyhint`, `eval`, sandboxed `shell` |
| 41 | Repository-scale change that lands or rolls back whole | multi-file patches are where agents silently corrupt repos; ARISE reports an 81% reduction in multi-file patches via structural grounding ([ARISE](https://arxiv.org/pdf/2605.03117), [MultiFixer](https://arxiv.org/abs/2607.26591v1), [SGAgent](https://arxiv.org/html/2602.23647v2)) | per-call checkpoint groups (14F1), atomic batch edits (34F1), `undo`, loop 28's graph, loop 31's worktrees |
| 42 | The small-model compiler | this repo's endpoint is 27B-class; open-weight models are already fine at *short-horizon structured* tool use and fall over on *long-horizon* coordination — so compile long horizons into short ones ([AgentFloor](https://arxiv.org/abs/2605.00334), [Devstral](https://arxiv.org/pdf/2509.25193), [Inside the Scaffold](https://arxiv.org/html/2604.03515v2)) | `tool_protocol: auto` + the prompt protocol, `argvalidate`, `slim`, `spill`, compaction strategies, `delegate` |
| 43 | The caller contract: codemonkey inside other agents' workflows | the intent doc's actual reason for existing is "scriptable by other agents"; MCP passed ~97M monthly SDK downloads by March 2026 and every major vendor speaks it ([protocol survey](https://arxiv.org/html/2505.02279v1), [Codex CLI interop](https://codex.danielvaughan.com/2026/05/01/codex-cli-agent-interoperability-protocols-mcp-acp-a2a/)) | `exec --json` JSONL, exit codes, `--output-schema`, `jobs`, `status`, the loop-10 MCP deferral |
| 44 | Trustworthy autonomy budgets | unattended usefulness is gated by *stopping*, not by capability; oversight itself has a capacity ([Agent Safety as a Runtime Contract](https://arxiv.org/html/2608.11274), [Oversight Has a Capacity](https://arxiv.org/html/2606.08919), [governance→runtime controls](https://arxiv.org/html/2604.05229)) | `permissions`, `approvals`, `cost`, `budget`, `jobs`, `sandbox`, `envquarantine` |
| 45 | The evidence pack + v4.0 closing acceptance | a run another agent cannot verify is a run a human must re-do by hand ([evidence tracing & provenance](https://arxiv.org/html/2606.04990v1), [VeriGraph](https://arxiv.org/html/2606.16603)) | the append-only journal, `claims`, `truthpass`, `redact`, `digest`, `eval` |

**The honest ratio.** 38 and 40 carry most of the expected value: 38 because it
converts sunk cost into live capability at zero design risk, 40 because a
machine-checkable success signal is what makes every other loop measurable on a
weak model. 41 and 44 are what make unattended use *safe enough to actually
leave running*, which is the difference between a demo and a tool. 43 is the
one the stated intent has been waiting for since loop 10. 42 is the highest
variance: it may find that the 27B endpoint's ceiling is the ceiling, and
R-G requires saying so in that case.

---

## §B — Two additional arc rules

R-A … R-G from the two predecessor proposals remain binding. Add:

**R-H — A certificate must be what it says it is.** `certify.m_certificate` is
a fixed-n Hoeffding bound evaluated after every observation; that is not
anytime-valid inference, and replaying it across a growing prefix inflates the
error rate ([testing by betting](https://arxiv.org/pdf/2504.00593),
[anytime validity](https://arxiv.org/pdf/2501.03982)). Any statistic this arc
calls a "certificate" is either time-uniform (a confidence sequence / test
supermartingale) or is renamed to what it actually is. The choice is recorded
with its coverage check, and the loop-30 numbers measured under the old bound
are re-stated under the new one or explicitly marked as superseded.

**R-I — A capability is not shipped until its entry point is exercised.** A
cycle's verify probe may not be satisfied by `pytest` alone. Every capability
cycle must carry at least one probe that drives the feature through
`codemonkey exec`, a `codemonkey` sub-command, or a tool call the model can
emit — and asserts an observable difference in the run (a tool invoked, a
number printed, a rule enforced, a file changed, a shorter context). Unit
tests remain required; they are no longer sufficient. Any capability that
cannot be given such a probe is, by that fact, not a capability — delete it
under R-A and record the deletion.

---

## CYCLE R38 — Loop 38: reachability — wire the orphans, or delete them

**Question.** Seven capability modules from loops 28–36 cannot affect a real
run. Which of them, once actually reachable, changes a measured number — and
which should be deleted? This loop adds **no new capability**; it discharges
`build/critic-r37.md` F7 and F8, and it is the entry condition for every
charter after it.

**Seeds.** `graph_query` / `graph_path` / `graph_explain` in `tools.SPECS` over
`graphify-out/graph.json`, with a staleness check against HEAD (a stale graph
is worse than none — the review found the graph two cycles behind). `certify`
called by `eval` so a suite can stop early with a stated certificate — under
R-H, which means fixing the bound first. `bestofn` behind an `exec --best-of N`
flag gated on a verify command, defaulting OFF per R-F. `rubrics` as an
optional per-task grader in the eval suite. `adaptivemem` and `learnedctx`
registered as *selectable strategies* in the loop-5 registry rather than
hard-wired, so the old behavior stays the default and the new one is
A/B-measurable. `branches` behind a `codemonkey branch` sub-command. And
`build/CAPABILITY_REGISTER.md` reconstructed as the arc's release record, one
row per capability: PROVEN-LIVE / UNIT-ONLY (with reason) / DEAD.

**Likely build** (candidate, not pre-approved): `src/codemonkey/tools/graph_*.py`,
`eval` certificate wiring, `exec --best-of`, two strategy registrations, one
sub-command, the register.

**Verify probe.** Per R-I, one entry-point probe per wired module, plus: the
register exists with a row for every module in `src/codemonkey/`, and at least
one module ends the loop marked **DEAD and deleted** if it cannot earn a probe.

**Entry condition.** R37F1–R37F6 committed (done). **Core-design: PARTIAL** —
new agent tools and new registry strategies extend approved surfaces rather
than change them; deleting a capability is reversible via git. The `--best-of`
flag spends N× tokens and therefore ends by asking, per R-F.

---

## CYCLE R39 — Loop 39: failure-anchored recovery

**Question.** The journal already types every failure (`error_class`) and
nothing reads it *during* a run. Failed trajectories are 12–82% longer than
successful ones — the agent keeps working long after the run stopped being
recoverable. Can the first unrecoverable step be localized *online*, and does
acting on it (retry differently, roll back to a checkpoint, escalate, stop)
beat running to `max_turns`?

**Seeds.** A failure taxonomy over the journal's existing classes, anchored to
the published nine-category framing (tool choice, argument correctness,
ambiguity, refusal calibration, stopping, recovery, state/memory, injection,
cost) — mapped to what this repo can actually observe, not adopted wholesale.
A recovery policy table: which class implies retry-with-different-args, which
implies checkpoint rollback (loop 14), which implies "stop and report" (the
most valuable and least implemented). Repeat-failure detection: the same
`(tool, error_class)` three times is a loop, not progress — and `compile_rules`
already mines exactly that signal offline. Honest stopping: an agent that ends
with "I could not do this, here is where I got stuck, here is the checkpoint"
is more useful than one that ends with a confident wrong patch.

**Verify probe.** Per R-I: a scripted failing scenario driven through
`codemonkey exec` where the pre-loop-39 agent burns its full turn budget and
the post-loop-39 agent stops early with a typed failure report — with the turn
count and token cost of both, per R-F.

**Entry condition.** R38 closed. **Core-design: PARTIAL** — a policy that can
*terminate* a run is adjacent to approval semantics; it ends by asking.

---

## CYCLE R40 — Loop 40: the test loop as the primary control signal

**Question.** On a 27B-class endpoint the weakest link is the model judging its
own work. A reproduction test moves that judgment into an exit code. Can the
agent be made to write the failing test *first*, and does gating the answer on
fail→pass beat the current self-report + optional verify command?

**Seeds.** A `reproduce` phase before the edit phase: from the task text,
generate a test that fails on the current tree (published reproduction-test
generators report ~63% fail-to-pass on TDD-Bench Verified — R-G requires
measuring this repo's rate on a 27B model, and it will be lower). Promotion of
the verify gate from optional to default-on when a test command is
discoverable, with `verifyhint` (already wired) doing the discovery. Test
quality as a first-class risk: a test that passes trivially is worse than no
test, so a generated test must be shown to fail before the fix and pass after.
Interaction with loop 32's best-of-N — a machine verifier is exactly what
best-of-N needs to be more than a coin flip, and the two together are the
arc's main quality lever on a weak endpoint.

**Verify probe.** Per R-I: on the golden eval suite, `exec` with the test loop
ON vs OFF — pass rate, token cost and wall-clock for both, certified per R-H,
plus the measured fail-to-pass rate of generated tests and the published number
alongside it per R-G.

**Entry condition.** R38 closed (certificates and best-of-N reachable).
**Core-design: PARTIAL** — making the verify gate default-on changes what
"finished" means; it ends by asking.

---

## CYCLE R41 — Loop 41: repository-scale change that lands or rolls back whole

**Question.** Multi-file changes are where an agent quietly corrupts a repo:
one hunk lands, its sibling does not, tests pass by accident. Structural
grounding is reported to cut multi-file patches by ~81%. Can a change be
planned as one unit — impact-analyzed against the graph, applied atomically,
rolled back whole on failure — and does that reduce partial-application?

**Seeds.** A change plan as an explicit object (files, hunks, order,
dependency between them) rather than a stream of `edit_file` calls. Change
impact analysis over loop 28's graph: which callers does this signature change
break (the graph knows; `search` guesses). Atomic apply built on the existing
per-call checkpoint *group* (14F1) extended to a whole plan, with `undo`
reversing the plan, not the last file. Loop 31's worktrees as the isolation
boundary for a risky plan. Partial-application as a measured failure mode:
count it before and after.

**Verify probe.** Per R-I: a scripted multi-file refactor through
`codemonkey exec` where an induced mid-plan failure leaves the tree **byte-identical
to its pre-plan state** (`git status` clean, `git diff` empty), and a
same-signature-change task where the graph-grounded plan touches the callers a
`search`-driven plan misses — with both counts reported.

**Entry condition.** R38 closed (graph tools + worktrees reachable), R39 closed
(a rollback needs a failure signal to trigger on). **Core-design: YES** — this
changes how edits are applied and what `undo` means. **R41 ENDS BY ASKING.**

---

## CYCLE R42 — Loop 42: the small-model compiler

**Question.** Open-weight models in this size class are reported to be
adequate at short-horizon structured tool use and to fall over on long-horizon
coordination. This repo's entire premise is a local 27B endpoint. Can the
scaffold *compile* long-horizon tasks into short-horizon segments the endpoint
can actually execute — and how much of the frontier gap does that close?

**Seeds.** Segment the task into short, individually verifiable units with an
explicit hand-off state between them (`jobs` is already a durable state file —
this is composition, not new machinery). Constrain the tool-call surface per
segment: the prompt protocol's failure mode is malformed or hallucinated calls,
and `argvalidate` already catches them after the fact — catch them before, by
advertising fewer tools per segment. Grammar/constrained decoding where the
endpoint supports it, prompt-protocol tightening where it does not. Measure the
capability ladder honestly: which tiers this endpoint clears, which it does not,
and — per R-G — what the published open-weight numbers say next to ours. An
acceptable outcome is "segmentation buys +N points and the long-horizon tier is
still out of reach", stated plainly.

**Verify probe.** Per R-I: the golden suite through `exec` with segmentation ON
vs OFF — pass rate, malformed-tool-call rate, token cost, wall-clock, certified
per R-H, with the published comparison per R-G.

**Entry condition.** R40 closed (without a machine success signal this loop
cannot be measured). **Core-design: PARTIAL** — per-segment tool restriction
changes the advertised tool surface mid-run; it ends by asking.

---

## CYCLE R43 — Loop 43: the caller contract

**Question.** `build/intent.md` names the actual users: *other agents* calling
`codemonkey exec` as a subprocess, and CI. Loop 10 deferred MCP. Meanwhile MCP
became the default plumbing between agents and tools (~97M monthly SDK
downloads by March 2026, native support from every major vendor), with ACP for
editors and A2A for agent-to-agent delegation. What does codemonkey have to
expose for another agent to drive it *reliably* — and is MCP now justified, or
is the honest answer still "a clean subprocess contract"?

**Seeds.** The subprocess contract first, because it is what already exists and
is under-specified: exit-code taxonomy, a stable JSONL event schema with a
version field, `--output-schema` guarantees, resumability, and what a caller
can rely on across releases. Then MCP as a *server* (codemonkey exposes
`exec`/`review`/`status` as tools to another agent) versus MCP as a *client*
(codemonkey consumes other servers' tools) — these are different products and
the loop must pick, with reasons, not build both. Capability advertisement in
the A2A "agent card" spirit: a machine-readable description of what this binary
can do, its sandbox levels and its cost. A conformance suite a caller can run
to check a codemonkey build behaves as documented — the deliverable that makes
the contract real rather than aspirational.

**Verify probe.** Per R-I: a second, independent process drives codemonkey
end-to-end using only the documented contract (no repo knowledge), and the
conformance suite passes against the released binary; the JSONL schema is
versioned and a deliberate schema change is shown to fail the suite.

**Entry condition.** R38 closed. **Core-design: YES** — a published contract
constrains every future loop, and an MCP surface is a new trust boundary.
**R43 ENDS BY ASKING.**

---

## CYCLE R44 — Loop 44: trustworthy autonomy budgets

**Question.** The gap between "useful for ten minutes with a human watching"
and "useful overnight" is not capability — it is *stopping*. Current guardrails
are pre-execution (sandbox, approvals, rules). What runtime contract lets a run
be left alone: a declared budget in tokens, wall-clock, turns, cost and blast
radius, enforced by the runtime, that halts and reports rather than degrading?

**Seeds.** Budgets as a declared contract at run start, checked by the runtime
(the `cost` ledger and `budget` calculator exist; nothing enforces them
mid-run). Blast radius as a first-class limit: files touched, directories
written, commands run — a run that suddenly touches 200 files should stop, and
loop 41's change plan makes that measurable in advance. Oversight capacity as a
design input, not an afterthought: an approval queue that fatigues its human is
a rubber stamp, so batch and rank what needs a human rather than asking per
call. The interaction with loop 34's self-authored rules — a rule the agent
proposed must never widen its own budget. Honest halting: a stopped run reports
what it did, what it did not, and how to resume (`jobs` already persists that).

**Verify probe.** Per R-I: a run with a declared token/turn/blast-radius budget
is halted by the runtime at the limit, exits with a distinct code, writes a
resumable job file, and leaves the workspace in a checkpointed state — plus a
probe asserting a self-authored rule cannot raise a budget.

**Entry condition.** R41 closed (blast radius needs a change plan to bound).
**Core-design: YES** — this defines what unattended operation *is*.
**R44 ENDS BY ASKING.**

---

## CYCLE R45 — Loop 45: the evidence pack + v4.0 closing acceptance

**Question.** Can a run hand its caller a self-contained, verifiable account of
itself — claims linked to the evidence that supports them, deterministic parts
reproducible without the model — and does the whole arc survive a closing
acceptance under R-A/R-E/R-I?

**Seeds.** An evidence pack per run: the claims the agent made (`claims`,
`truthpass` already extract them), each linked to the journal record, command
output, diff or test result that supports it, redacted (`redact`) and packaged
so another agent can check it without re-running the model. Hash-chaining the
append-only journal so the pack is tamper-evident. Reproducibility of the
deterministic half: same inputs, same tools, same result. Then the closing
work: `build/CAPABILITY_REGISTER.md` complete with no UNVALIDATED rows,
every loop-38..44 row carrying LOCAL / PUBLISHED / GAP per R-G and its cost per
R-F, deletion cycles for anything that failed its certificate, a closing critic
pass, `THREAT_MODEL.md` refreshed (MCP surface, autonomy budgets and evidence
packs each change the security surface), final BUILD_REPORT, tag v4.0, Gate 5
handoff.

**Verify probe.** `bash build/acceptance_sweep.sh` → all exit 0, zero BLOCKED;
`uv run pytest -q` → exit 0; `uv run codemonkey --version` matches the tag;
every register row reads PROVEN-LIVE, UNIT-ONLY with a stated reason, or DEAD;
an evidence pack from a real run verifies in a separate process with the model
endpoint switched off.

**Entry condition.** Loops 38–44 closed (shipped, or explicitly rejected in
writing), no open critic finding above LOW. **Core-design: NO.**

---

## §C — What this arc deliberately does not do

- **No new model-capability research.** Loops 28–36 already bought nine
  techniques; seven of them have never run. Buying a tenth before wiring those
  is how this repo got here.
- **No frontier-model assumptions.** Every published number cited above was
  obtained on larger models and different harnesses. R-G is binding: state the
  published number, measure ours, report the gap.
- **No silent scope growth.** Four of the eight charters (R41, R43, R44 outright;
  R38/R39/R40/R42 in part) touch approved core design and **end by asking**, per
  AGENTS.md §4. This proposal grants no authorization to anything.

**Status: PROPOSED, NOT AUTHORIZED.** `CYCLE R38`–`R45` are appended unchecked
to `build/plan.md`. They stay unchecked until the user authorizes the arc.
