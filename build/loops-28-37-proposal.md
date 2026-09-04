# Proposed forward loops 28–37 — the capability arc (NOT AUTHORIZED)

Date: 2026-09-03. Author: SOTA survey pass requested by the user, after the
loops 17–27 debt arc was judged too conservative to be the whole forward plan.
Baseline assumed at entry: loop 27 closed (v2.0), `build/CAPABILITY_REGISTER.md`
current, suite green.

**Predecessor arc.** `build/loops-17-27-proposal.md` — the debt arc. Its §0
handoff contract, §1 verified current state, §2 debt ledger (D1–D12) and §3
arc rules (R-A … R-E) **apply unchanged here** and are not restated. Read that
file first; this one adds the charters and two extra rules (R-F, R-G).

**What this arc is.** Loops 17–27 make the machine *honest*. This arc makes it
*current*. Every charter below is anchored to 2026 literature with a cited
result, and every one of them is chosen because **CodeMonkey already ships the
primitive and never composed it** — the work is composition and measurement,
not green-field architecture. Where a technique's published result was
obtained on a frontier model and this repo runs a 27B-class local endpoint,
the charter says so, because that gap is the single largest threat to every
number in this arc.

---

## §A — Why these ten, and what makes them cheap here

| Loop | Technique | Published anchor | Primitive already in the repo |
|---|---|---|---|
| 28 | Graph-grounded retrieval | Tree-sitter KG cut agent tokens ~10× and tool calls 2.1× across 31 repos ([code-graph indexing](https://anthonywest.co.uk/research/code-intelligence-indexing-2026-openai), [Code Isn't Memory](https://arxiv.org/abs/2606.22417)) | `graphify-out/` is built, committed and current — and the agent cannot read it |
| 29 | LSP grounding + pre-apply validation | Lint-before-apply editing and LSP symbol navigation in current scaffolds ([Inside the Scaffold](https://arxiv.org/html/2604.03515v2)) | `edit_file`, `search`, sandbox, per-call checkpoints |
| 30 | Certified, comparable measurement | Anytime-valid certificates ([2607.00871](https://arxiv.org/pdf/2607.00871)); DeepSWE separates agents across a 69.8-pt band ([DeepSWE](https://arxiv.org/html/2607.07946v1), [SWE-EVO](https://arxiv.org/html/2512.18470v6)) | eval harness, golden suite, baselines, cost ledger |
| 31 | Fork-and-branch execution | Checkpoint reuse cut rollout tokens 40.0–64.2% ([Crab](https://arxiv.org/html/2604.28138)); fork-based agent fan-out ([Modal survey](https://modal.com/resources/best-sandboxes-swe-bench-coding-agents)) | per-call checkpoints + idempotent journal replay + `undo` |
| 32 | Best-of-N with an execution verifier | `p → 1−(1−p)^N`; hybrid execution/execution-free verification ([R2E-Gym](https://arxiv.org/pdf/2504.07164)) | `delegate_batch`, the cycle-19 verify gate, cost ledger |
| 33 | Generative + rubric verifiers, step-level rewards | Generative verifiers beat regressive ones across model sizes ([R2E-Gym](https://arxiv.org/pdf/2504.07164)); agentic rubrics as contextual verifiers ([2601.04171](https://arxiv.org/pdf/2601.04171)); rubric process rewards + heuristic test-time scaling ([SWE-TRACE](https://arxiv.org/pdf/2604.14820)) | `delegate role=critic`, `review`, the journal's per-step intents |
| 34 | Corrections compiled into enforcement | User corrections → runtime enforcement ([2606.13174](https://arxiv.org/pdf/2606.13174)) | the ordered deny→ask→allow permissions engine + `lessons` |
| 35 | Adaptive memory management | SWE-MeM ([2606.28434](https://arxiv.org/pdf/2606.28434)); continual learning ([SWE-Bench-CL](https://arxiv.org/pdf/2507.00014)); memory transfer ([2604.14004](https://arxiv.org/pdf/2604.14004)) | strategy registry (memory + compaction), `lessons`, spill, slim |
| 36 | Learned context assembly | Meta Context Engineering: 89.1% vs 70.7% on SWE-bench Verified ([Inside the Scaffold](https://arxiv.org/html/2604.03515v2)) | `repomap`, `slim`, `spill`, compaction strategies, loop 28's graph |
| 37 | v3.0 closing acceptance | — | the register, the sweep, the critic gate |

**The honest ratio.** 28 and 34 are the cheapest relative to payoff — both are
one composition away from surface that already exists. 32 is the largest
single quality lever *specifically because* the endpoint is weak: parallel
scaling pays most where single-shot `p` is low. 36 is the most speculative and
is deliberately last.

---

## §B — Two additional arc rules

Rules R-A … R-E from `build/loops-17-27-proposal.md` §3 remain binding. Add:

**R-F — Cost is half the result.** Every quality number in this arc is
reported next to its cost multiplier and wall-clock, per arc rule R-A's raw
numbers. Best-of-N at N=8 that lifts pass rate 12 points is a *different*
finding from one that does it at N=2. A cycle that reports a delta without its
token and wall cost has not met its verify probe. Adoption defaults to OFF for
anything above 2× cost until a config-declared budget opts in.

**R-G — Replicate, then report the gap.** Each charter cites a published
result obtained on other models and other harnesses. The research cycle states
the published number, the cycle measures this repo's number, and the report
records **both plus the gap**, with a hypothesis for any large divergence
(model class, task set, harness). "We got 10×" and "we got 1.4× and here is
why" are both acceptable outcomes. Silently reporting only the local number,
or citing the published number as if it were ours, is a fabrication under
SPRINT.md's hard rules.

---

## CYCLE R28 — Loop 28: graph-grounded retrieval

**Question.** This repo builds, commits and maintains a structural knowledge
graph in `graphify-out/`, and `AGENTS.md` requires *human-side* agents to query
it before reading files — while the agent this project ships navigates by
`search`, `glob` and a heuristic `repo_map`. Does exposing the structural index
to the agent itself reproduce the published retrieval win (~10× tokens, 2.1×
tool calls across 31 repos), and by how much on a 27B-class model?

**Seeds.** `graph_query` / `graph_path` / `graph_explain` as first-class tools
over `graphify-out/graph.json`, mirroring the CLI the contract already
mandates. `repo_map` ranking re-grounded on graph structure (call/import edges,
communities) instead of heuristics. Graph freshness as a correctness concern —
a stale graph is worse than none, so staleness must be detected and reported,
not silently trusted. Retrieval scoping: what a delegate scout returns
(loop 11's role) when it can traverse rather than grep. Behavior when the graph
is missing (a stranger's repo — loop 18 will have evidence) — build it, degrade
to `repo_map`, or refuse.

**Likely build** (candidate, not pre-approved): `src/codemonkey/tools/graph_*.py`,
a staleness check against HEAD, `repomap.py` ranking swap behind a config flag.

**Entry condition.** `graphify-out/graph.json` present and current at HEAD, and
the harness can score two retrieval arms (loop 21 closed). Otherwise R28
records BLOCKED.

**Core-design flag: PARTIAL** — new tools sit inside the tool registry; changing
`repo_map`'s ranking changes context assembly and ends by asking.

**Exit.** `build/research-loop28.md` + `loop28:` cycles, each reporting tokens
and tool calls per task for graph-on vs graph-off arms, against the published
~10×/2.1× figures per rule R-G.

---

## CYCLE R29 — Loop 29: LSP grounding and pre-apply validation

**Question.** Edits are applied first and discovered to be broken later, at the
cost of a turn, a checkpoint and often a retry. Current scaffolds validate the
edit before it lands and navigate by symbol rather than by text. What does
symbol-accurate navigation and pre-apply validation buy on this codebase, and
what does it cost per edit?

**Seeds.** A language server (Python first: pyright / pylsp) behind a thin
client, offline-installable. Symbol-level navigation tools — definition,
references, callers — replacing textual `search` for symbol questions. Edit
validation *before* apply: syntax, then lint, then typecheck, with the edit
rejected and returned to the model rather than committed and undone. Failure
budget: how many validation retries before the turn gives up. Multi-language
posture — either it degrades cleanly on a repo with no server or it is
Python-only *and says so*. Interaction with loop 28's graph (both answer "where
is this symbol used", one statically, one structurally — the loop must decide
which is authoritative rather than shipping both and confusing the model).

**Likely build:** an `lsp.py` client, `find_definition`/`find_references`
tools, a pre-apply validation hook in `edit_file`/`write_file`.

**Entry condition.** A language server installable in this environment without
network access at run time. If not, R29 narrows to syntax+lint validation
(which needs no server) and records the LSP portion BLOCKED.

**Core-design flag: PARTIAL** — new tools are registry work; making an edit
*conditional* on typecheck changes edit semantics and ends by asking.

**Exit.** `build/research-loop29.md` + `loop29:` cycles with before/after
broken-edit rate and per-edit latency.

---

## CYCLE R30 — Loop 30: certified and comparable measurement

**Question.** Loop 21 made measurement affordable; this arc will make eight
separate quality claims on a slow single endpoint, and the golden suite is
homemade so none of its numbers can be compared to anything published. What
makes a claim in this arc both *cheap to certify* and *comparable to the
field*?

**Seeds.** Anytime-valid sequential certificates — stop as soon as significance
is reached instead of pre-committing to N, which is the difference between
affordable and unaffordable on a 27B local endpoint. Adoption of a real
benchmark subset (DeepSWE, SWE-EVO, or SWE-Bench Pro) alongside the golden
suite, with an explicit feasibility assessment first: these harnesses are
container-heavy and long-horizon, and a 27B local model may simply not
complete them — an honest "we can run this 40-task subset and no more" is the
expected outcome, not full-suite numbers. A standing arm-comparison report
format that carries cost per rule R-F. A regression gate so a later loop cannot
silently undo an earlier loop's win.

**Likely build:** a sequential-test module in the eval harness, a benchmark
adapter + pinned task subset, a report template, a CI-shaped regression check.

**Entry condition.** Loop 21 closed. Benchmark adoption additionally needs a
container runtime and disk; without it, that half records BLOCKED and the
certificates half proceeds (it needs neither).

**Core-design flag: NO.**

**Exit.** `build/research-loop30.md` + `loop30:` cycles; the certificate
machinery is then **mandatory for every quality claim in loops 31–36**.

---

## CYCLE R31 — Loop 31: fork-and-branch execution

**Question.** Exploring N alternatives today means N full runs that re-execute
an identical prefix. Published checkpoint-reuse runtimes cut rollout tokens
40.0–64.2% by resuming branches from shared intermediate state. This repo
already snapshots per call and replays its journal idempotently. What is the
smallest honest `branch` primitive — fork an in-flight run at a point, explore,
keep one, discard the rest — and what exactly is shared versus copied?

**Seeds.** A branch point defined against the existing checkpoint + journal
pair, so a branch is a *replayable* object rather than a copy of a process.
What is shared: the transcript prefix, the KV/prompt-cache prefix (the cache
telemetry from loop 5 measures whether that sharing actually pays), the
filesystem snapshot. What must be copied: anything mutable a branch writes.
Discard semantics — a losing branch must leave nothing behind, which is `undo`
plus a proof. Journal thread identity for branches, so forensics can still
reconstruct what happened. Explicit non-goal: microVM-level forking is
infrastructure this project does not own; the primitive here is process-level
and file-level.

**Likely build:** `branch` support in `checkpoints.py` + `journal.py`, an
internal API `fork_run(at=...)`, discard/keep with a residue assertion.

**Entry condition.** Loop 19 closed (crash and replay semantics defined) and
loop 24 closed (concurrent writers safe) — branching is concurrency plus
resume, and inherits both. If either was BLOCKED, R31 records BLOCKED rather
than building forking on undefined crash semantics.

**Core-design flag: YES** — forking in-flight run state is session and journal
semantics. R31 ENDS BY ASKING.

**Exit.** `build/research-loop31.md` + `loop31:` cycles, each with a
token-reuse measurement against the published 40–64% band (rule R-G) and a
zero-residue probe for discarded branches (exact file-state comparison).

---

## CYCLE R32 — Loop 32: best-of-N with an execution verifier

**Question.** Under independent attempts, resolve probability goes
`p → 1−(1−p)^N`. This project runs a 27B-class local model where single-shot
`p` is low — the regime where parallel scaling pays most, and where cheap local
tokens are the currency being spent. Does best-of-N with an execution verifier
lift the harness materially, at what N, and at what cost multiplier?

**Seeds.** Fan-out over `delegate_batch` with N independent attempts at one
task. Verification: run the task's verify command against each candidate
(execution-based) and rank; fall back to execution-free reranking where no test
exists (loop 33 owns the scoring model). Isolation — N candidates mutating one
working tree is the failure mode that makes this dangerous, so each candidate
needs loop 31's branch or a separate tree, and loop 20's containment is what
keeps a bad candidate from reaching outside it. Selection policy and ties.
Cost: N× tokens is the headline objection and must be reported per rule R-F,
including the "N cheap local attempts vs 1 frontier API call" comparison, which
is the actual economic argument. Early-abort: stop fanning out once a candidate
passes verification.

**Likely build:** `exec --best-of N` (default 1), a candidate-selection module,
verify-driven ranking, per-candidate isolation via loop 31.

**Entry condition — hard.** Loop 20 (containment) and loop 31 (branching) both
closed. Without containment, N concurrent mutating workers is a defect, not a
feature: R32 then narrows to **read-only fan-out** (analysis/review tasks that
mutate nothing) and records the mutating case BLOCKED.

**Core-design flag: YES** — "one prompt produces N runs and one answer" changes
what a run is, and multiplies cost. R32 ENDS BY ASKING.

**Exit.** `build/research-loop32.md` + `loop32:` cycles with pass rate, tokens
and wall at N ∈ {1, 2, 4, 8}, certified by loop 30's sequential test, and the
observed curve compared to the theoretical `1−(1−p)^N` (rule R-G).

---

## CYCLE R33 — Loop 33: generative verifiers, rubrics, step-level rewards

**Question.** Loop 32's selection is only as good as its verifier, and many
real tasks have no test to run. The 2026 finding is that *generative* verifiers
outperform regressive ones across model sizes, that agentic rubrics work as
contextual verifiers where execution cannot, and that rubric process reward
models plus heuristic test-time scaling improve long-horizon agents. Can a 27B
model verify its own candidates well enough to beat random selection — and is
step-level scoring worth its cost over outcome-only scoring?

**Seeds.** A generative verifier built on `delegate role=critic`, scoring a
candidate patch in [0,1] with a justification. Task-specific rubrics as the
contextual verifier when no test exists (loop 11's critic role is the delivery
vehicle; the rubric is the new part). Hybrid scoring: execution result
dominates, rubric breaks ties. Step-level process rewards over the journal's
per-step intents, and heuristic test-time scaling — spend more compute at
high-uncertainty steps only. The falsification that matters: **verifier
accuracy versus ground truth**, measured directly, because a verifier that is
worse than random makes best-of-N actively harmful and that must be discovered
here rather than inferred from a pass-rate wash.

**Likely build:** a verifier module with rubric templates, hybrid scoring in
loop 32's selector, optional step-level scoring behind a flag.

**Entry condition.** Loop 32 closed (there is a selection point for a verifier
to improve) and loop 30's certificates exist.

**Core-design flag: PARTIAL** — a model-scored gate that decides whether work is
accepted is adjacent to approval semantics; that specific use ends by asking.
Scoring that only *ranks* candidates does not.

**Exit.** `build/research-loop33.md` + `loop33:` cycles reporting verifier
accuracy against known-good/known-bad candidates first, then end-to-end
selection quality versus random and versus execution-only.

---

## CYCLE R34 — Loop 34: corrections compiled into enforcement

**Question.** When a user corrects this agent, the correction survives as prose
— a lesson the model may or may not honor next time. Published work compiles
user corrections into *runtime enforcement*. This repo has the rare half
already: an ordered `deny → ask → allow` permissions engine with glob matching
and journal-recorded rule hits. What class of correction can be compiled into a
rule that mechanically cannot be violated, and what must stay advisory?

**Seeds.** A taxonomy of corrections: mechanically enforceable ("never touch
`migrations/`", "no `git push`"), partially enforceable ("prefer `edit_file`
over `write_file` for files over N lines" — enforceable as a deny with a
message), and irreducibly advisory ("be more careful about naming"). Compilation
path: correction → proposed rule → **user confirmation before it binds** (a
silently self-authored deny rule is a footgun) → `permissions.rules` entry with
provenance. Rule lifecycle: expiry, conflict with existing rules, precedence,
and a `codemonkey rules` surface to list/explain/revoke — an enforcement layer
nobody can audit is worse than none. The measured claim: repeat-violation rate
for a corrected behavior, before and after compilation.

**Likely build:** a rule-synthesis module bridging `lessons.py` and
`permissions.py`, provenance fields on rules, `codemonkey rules
list|explain|revoke`, a confirmation gate.

**Entry condition.** Loop 21's verdict on `lessons` is recorded — if lessons
were deleted there, this loop builds on the permissions engine alone, which is
sufficient. Real correction data helps; loop 18's friction log and the journal
supply it.

**Core-design flag: PARTIAL** — rules that the agent authors for itself change
what the permission layer *is* (a user-authored policy vs a learned one), and
that ends by asking.

**Exit.** `build/research-loop34.md` + `loop34:` cycles, including a probe that
replays a corrected scenario and asserts the violation is now **refused by the
permission layer**, not merely avoided by the model.

---

## CYCLE R35 — Loop 35: adaptive memory management

**Question.** Memory here is a curated file plus tag-overlap lesson retrieval;
the 2026 line of work is adaptive, learned memory management for long-horizon
agents, continual learning across a task stream, and memory that transfers
across domains. With loops 19/24/25 producing multi-day jobs and a large
journal corpus, does adaptive management beat the current heuristics — and does
anything transfer to a repo the memories did not come from?

**Seeds.** Adaptive write/retain/evict policy over the memory + lessons stores,
replacing fixed heuristics. Continual-learning framing: performance over a
*sequence* of related tasks, not one task in isolation — which requires a task
stream the harness does not have today. Cross-domain transfer, tested honestly
against loop 18's foreign repos, since the failure mode is memories that help
on the source repo and mislead elsewhere. The privacy posture for any
cross-repo store (already flagged at R13 as core-design). The anti-goal
inherited from R13: no silent behavior change without a probe showing the
delta.

**Likely build:** an adaptive memory strategy in the existing registry, a
task-stream eval mode, transfer measurements across repos.

**Entry condition.** Loop 25 closed (retention policy exists — an adaptive
memory that fights a GC policy is unmeasurable) and ≥2 repos' worth of history
exists (loop 18). R35 must be willing to close with a documented "no", exactly
as R13 was.

**Core-design flag: PARTIAL** for a new strategy in the registry; **YES** for a
cross-repo store — that ends by asking.

**Exit.** `build/research-loop35.md` + `loop35:` cycles with task-stream
results certified by loop 30, or a documented rejection with the numbers.

---

## CYCLE R36 — Loop 36: learned context assembly

**Question.** Published context-engineering work reports 89.1% versus 70.7% on
SWE-bench Verified against hand-engineered baselines — a larger delta than most
model upgrades. This repo assembles context from hand-tuned parts: `repo_map`,
`slim`, `spill`, compaction strategies, memory injection, and (after loop 28)
the graph. Is there a measurable win in making assembly a policy that is
*selected and scored* rather than hand-ordered?

**Seeds.** Context assembly as an explicit, swappable policy with a scored
matrix (loop 5's strategy matrix is the existing vehicle). Per-task-class
assembly — a review task and an edit task do not want the same window. Budget
allocation across sources under a token ceiling. Interaction with loop 28's
graph retrieval and loop 35's memory, both of which are context sources, so
this loop is where they compete for space. The honest risk, stated up front:
the published number comes from a frontier model with a large window, and a
27B-class model with a smaller one may show a fraction of it or none — rule
R-G governs the report.

**Likely build:** a context-assembly policy interface in the strategy registry,
2–3 competing policies, matrix scoring, a config-selected default.

**Entry condition.** Loops 28, 30 and 35 closed — every major context source
exists and can be scored. This is the most speculative charter in the arc and
is deliberately last; if the arc's budget runs out, this is the loop to drop.

**Core-design flag: YES** — context assembly is the architecture the whole CLI
is built around. R36 ENDS BY ASKING.

**Exit.** `build/research-loop36.md` + `loop36:` cycles with per-policy scores
certified by loop 30, and the gap to the published 89.1/70.7 result explained.

---

## CYCLE R37 — Loop 37: v3.0 closing acceptance

**Question.** After ten capability loops, which techniques are actually carried
by evidence produced *here*, and what does a release record look like when
every headline feature is a replication of someone else's published result?

**Seeds.** Full A1–A20 plus every loop-2..36 criterion, live, zero BLOCKED or
an individually justified exception list. `build/CAPABILITY_REGISTER.md` current,
with every loop 28–36 row carrying its local number, the published number, and
the gap (rule R-G). A cost table per rule R-F: what each adopted technique
multiplies. Deletion cycles for anything that did not survive its own
certificate — this arc must be capable of subtracting, as loop 21 was. A
closing critic pass in `build/critic-cycle6.md` style. `THREAT_MODEL.md`
refreshed — best-of-N, branching and self-authored permission rules all change
the security surface, and loop 34's rules in particular are a new trust
boundary. Final `BUILD_REPORT.md` for loops 28–37, tag, Gate 4 handoff.

**Entry condition.** Loops 28–36 closed (shipped, or explicitly rejected /
BLOCKED in writing), no open critic finding above LOW, live endpoint reachable.

**Core-design flag: NO.**

**Exit.** `build/research-loop37.md` + `loop37:` cycles ending in
`loop37-final`: the closing record, the register at final state, the tag, the
Gate 4 handoff.

---

## What this arc deliberately does not do

- **It does not authorize anything.** `R28`–`R37` are appended to
  `build/plan.md` unchecked and stay unchecked until the user authorizes them.
- **It does not skip the debt arc.** Loops 31, 32 and 35 have hard entry
  conditions on loops 19, 20, 24 and 25 — not as bureaucracy, but because N
  concurrent mutating workers without containment is a defect, and branching
  without defined crash semantics is undefined behavior.
- **It does not assume the published numbers.** Every one was obtained on other
  models and other harnesses. Rule R-G exists so a 1.4× where the paper saw
  10× is reported as a finding, not buried.
- **It does not chase infrastructure this project does not own.** MicroVM
  forking, hosted sandboxes and RL training runs are out of scope; the
  primitives here are process-level and file-level.
- **It does not treat "state of the art" as a reason to ship.** Rule R-A still
  governs: measured or deleted. A technique that does not separate on this
  endpoint is a documented "no" — which, on a 27B-class local model, is a
  genuinely likely outcome for at least two of these ten loops.
