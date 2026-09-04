# Proposed forward loops 46–50 — the compounding arc (NOT AUTHORIZED)

Date: 2026-09-04. Author: forward-planning pass requested by the user with the
brief "items that can truly 10x the utility of codemonkey … go to the web and
look at the state of the art and find what would make CodeMonkey truly unique
and epic."

**Predecessor arcs.** `build/loops-17-27-proposal.md` (debt),
`build/loops-28-37-proposal.md` (capability), `build/loops-38-45-proposal.md`
(utility). Their §0 handoff contract, §2 debt ledger and arc rules
**R-A … R-I apply unchanged here** and are not restated. Read all three first;
this file adds two rules and five charters, and it **begins after loop 45's
v4.0 acceptance** — nothing here may be built while loops 38–45 are open.

---

## §0 — The finding this arc is built on

The utility arc (38–45) is about making CodeMonkey's *existing* abilities reach
a real run: wiring orphans (38), noticing failure (39), trusting a test instead
of a model's opinion (40), landing multi-file change whole (41), compiling long
horizons for a small model (42), being callable by other agents (43), stopping
safely (44), and proving what happened (45). Every one of those makes a **single
run** better.

Add them all up and CodeMonkey is a very good scriptable coding agent whose
1,000th run on a repo is exactly as good as its first.

> **The multiplier this arc goes after is the only one the previous four arcs
> left on the table: a run that makes the next run cheaper. Loops 38–45 raise
> the ceiling of one run; 46–50 make the ceiling rise on its own, per repo,
> from ordinary use.**

That is also the honest answer to "what would make CodeMonkey unique." Not
another tool — the field's frontier scaffolds already have better tools than
this repo will. What almost nothing in the field has is a *local, auditable,
revocable* accumulation surface: this repo already ships an append-only journal
(`journal.py`), a verified-by-eval lesson gate (`lessons.py`,
`lessons_gate.py`), rule compilation into enforcement (`compile_rules.py`), a
measurement harness (`eval.py`, `rubrics.py`, `certify.py`), a strategy
registry with A/B-selectable domains (`strategies/`), a code graph
(`graphquery.py`) and per-call checkpoint groups (`checkpoints.py`). The
published techniques below have no home in most scaffolds. They have a home
here.

**The published headline this arc is chasing.** Live-SWE-agent starts from a
bash-only scaffold and *synthesizes its own tools during the run*, reaching
**75.4%** on SWE-bench Verified and **45.8%** on SWE-Bench Pro — the best known
open-source result — and its authors name a persistent, indexed **skill
library** as the obvious next step they did not take
([Live-SWE-agent](https://arxiv.org/pdf/2511.13646)). ACE turns context into an
incrementally-curated playbook and reports **+10.6%** on agent benchmarks
without labeled supervision ([ACE, ICLR 2026](https://arxiv.org/abs/2510.04618)).
PDR+RTV lifts Claude-4.5-Opus **70.9 → 77.6%** on SWE-bench Verified and
**46.9 → 59.1%** on Terminal-Bench v2 purely at test time
([Scaling Test-Time Compute for Agentic Coding](https://arxiv.org/abs/2604.16529)).
Those are the three biggest published deltas available to a scaffold that
cannot retrain its model — which is exactly this repo's situation.

---

## §A — The five charters

| Loop | Charter | Why it can actually 10x | Published anchor | Primitive already in the repo |
|---|---|---|---|---|
| 46 | **The skill library**: the agent synthesizes a tool mid-run, and a verified one is admitted to a repo-local, revocable library that later runs load | the single largest published scaffold-only delta (bash-only → 75.4% SWE-bench V); and the paper's own stated gap is persistence, which this repo's admission machinery already knows how to do | [Live-SWE-agent](https://arxiv.org/pdf/2511.13646), [MUSE-Autoskill](https://arxiv.org/pdf/2605.27366), [CoEvoSkills](https://arxiv.org/html/2604.01687) | `tools/__init__.py` `_MODULES`/`SPECS`/`PARAMS` registry, `sandbox.py` classification, `shell`, `delegate`, `eval` |
| 47 | **The evolving playbook**: generator → reflector → curator over *delta* updates to a durable, per-repo playbook | +10.6% agents / +8.6% finance with no labels, learning from execution feedback the journal already records; fixes the two failure modes (brevity bias, context collapse) that this repo's rewrite-style lessons file is exposed to | [ACE](https://arxiv.org/abs/2510.04618), [production lessons](https://contextual.ai/blog/optimize-agent-performance-using-self-evolving-context), [reflective experience](https://arxiv.org/pdf/2603.16843) | `lessons.py` + `lessons_gate.py`, `compile_rules.py`, `learnedctx.py`, `adaptivemem.py`, `journal.py` |
| 48 | **Parallel-distill-refine**: N rollouts → structured summaries → recursive tournament selection → one refinement pass | +6.7pt SWE-bench V / +12.2pt Terminal-Bench at test time; and it is the *correct* form of loop 38's `--best-of`, whose first-verifier-pass-wins rule throws away N−1 rollouts' worth of evidence | [PDR + RTV](https://arxiv.org/abs/2604.16529) | loop 38's `bestofn.py`, `branches.py` worktrees, `digest.py` (structured summaries), `jobs.py`, `matrix.py` |
| 49 | **Provenance-gated persistence**: tool output is taint-tracked, and nothing untrusted may author what loops 46–47 persist | 46 and 47 create the first artifacts that *outlive a run*; OWASP LLM01 remains the #1 agentic failure in production and 28 of 53 tracked agentic projects are coding agents — an injected instruction that reaches a skill or a playbook entry is not a bad turn, it is a permanent one | [OWASP/production data](https://www.helpnetsecurity.com/2026/06/11/owasp-prompt-injection-ai-security-failures/), [agentic security survey](https://arxiv.org/pdf/2510.06445), [MOSAIC CLI-composition attacks](https://arxiv.org/pdf/2607.02857), [out-of-band defenses](https://arxiv.org/pdf/2606.26479) | `envquarantine.py`, `permissions.py`, `approvals.py`, `redact.py`, `sandbox.py`, `truthpass.py`, `claims.py` |
| 50 | **Did it actually learn?** — continual-learning measurement + long-horizon suite + v5.0 acceptance | the arc's whole claim is compounding; a single accuracy number cannot show compounding, and the long-horizon regime is where the real gap lives (SOTA ~21–25% on SWE-EVO vs ~65–73% on SWE-bench Verified) | [SWE-Bench-CL / CL-F1](https://arxiv.org/pdf/2507.00014), [SWE-EVO](https://arxiv.org/abs/2512.18470), [harness engineering](https://lilianweng.github.io/posts/2026-07-04-harness/) | `eval.py`, `certify.py`, `rubrics.py`, `matrix.py`, `sessions.py`, `journal.py`, `status_mod.py` |

**The honest ratio.** 46 and 47 carry the arc's expected value: they are the
two places where a run can leave something behind that a later run picks up.
48 is the highest *certain* delta but the least novel — it is compute for
accuracy, and R-F means it ships OFF by default. 49 is not optional and is not
padding: it is the precondition that makes 46 and 47 safe to leave on, and if
49 cannot be built then 46 and 47 must ship read-only-by-default and say so.
50 is where R-A is enforced against this arc itself — if forward transfer is
not measurable, the arc's central claim is withdrawn in writing, not softened.

**What this arc deliberately does not do.** It does not let the agent rewrite
its own scaffold source, even though the Darwin Gödel Machine reports 20% → 50%
on SWE-bench from exactly that ([DGM](https://arxiv.org/pdf/2505.22954)).
Self-modification of `src/codemonkey/` is a core-design change; AGENTS.md
"Honor gates" requires stopping and asking, and the bounded form — synthesized
*tools* in a quarantined library, never edits to the loop — is what loop 46
charters instead. If the user wants the unbounded version, that is a separate
authorization, not a silent expansion.

---

## §B — Two additional arc rules

R-A … R-I from the three predecessor proposals remain binding. Add:

**R-J — Nothing the agent writes about itself is trusted until it is earned,
and everything it writes is revocable.** Any artifact authored by a run that
*persists into later runs* — a synthesized tool, a playbook delta, a promoted
lesson, a cached plan — enters **quarantined**, is admitted only by a
mechanical gate (its own probe passing, or a measured eval delta, never a model
saying it is good), records the run id and the input provenance that produced
it, and is removable by exactly one documented command that restores the prior
behavior. A library the user cannot audit and roll back is a liability, not a
capability; and per R-A, an admitted artifact that stops earning its gate is
evicted, not grandfathered.

**R-K — "Learned" is a measured word.** A loop may claim the agent learned
something only with (a) forward transfer — performance on tasks *after* the
artifact was admitted, versus the same tasks with the library disabled — and
(b) a retention check on an earlier held-out suite, showing the new artifact
did not degrade it, under R-H's time-uniform statistic. Report both or use the
word "changed". A raw pass-rate improvement measured on the tasks that produced
the artifacts is contamination, and the arc says so out loud.

---

## §C — The five charters in detail

### CYCLE R46 — Loop 46: the skill library

**Question.** When a run synthesizes a helper (a repo-specific search, a
fixture builder, a log parser) and that helper demonstrably worked, what has to
be true for the *next* run to get it for free — without turning the tool
registry into an unaudited attack surface?

**Seeds.** A `skill_create` tool that writes a candidate into a quarantined
`.codemonkey/skills/` with a mandatory self-probe; an admission gate that runs
the probe in the existing sandbox and promotes only on exit 0; loading admitted
skills into `SPECS`/`PARAMS` at run start behind `strategies.skills`
(default OFF, R-F); `codemonkey skills list|show|revoke|disable`; eviction of a
skill whose probe stops passing (R-A); every entry carrying originating run id
and provenance (R-J).

**Verify probe shape (R-I).** A live `exec` run that solves a task, synthesizes
a skill and admits it; a *second* `exec` run on a related task whose `--json`
tool trace contains the synthesized skill name and which finishes in strictly
fewer turns than the same task with `--no-skills`. BLOCKED + reason if the
endpoint is down; the admission gate and revocation still probe offline.

### CYCLE R47 — Loop 47: the evolving playbook

**Question.** This repo already turns run history into lessons and compiles
lessons into enforcement. ACE says the wins come from *delta* curation, not
rewriting — and that rewriting is what causes context collapse. Which of
CodeMonkey's five accumulation surfaces (lessons, rules, memory, learnedctx
fragments, playbook) should exist, and which should be deleted into the others?

**Seeds.** A reflector pass over the journal's typed step records producing
candidate deltas (add / demote / merge, never wholesale rewrite); an
append-only playbook with per-entry hit counts and eviction; the existing
`lessons_gate` verified-by-eval mechanism as the curator's admission gate; the
playbook injected through loop 38's `context` strategy domain so it is
A/B-measurable; **and a consolidation verdict** — R-A applied to CodeMonkey's
own overlapping learning surfaces.

**Verify probe shape (R-I).** Two runs of the same failing task: the first's
reflector emits a delta that the curator admits; the second's system prompt
provably contains it and the run avoids the first run's failing step. Plus a
context-collapse regression: 50 synthetic curation rounds leave the playbook's
early domain insights present (byte-checked), which a rewrite loop does not.

### CYCLE R48 — Loop 48: parallel-distill-refine

**Question.** Loop 38 ships `--best-of N`: run N attempts, first one that
passes the verify command wins, discard the rest. PDR says the discarded
rollouts are the valuable part. What does CodeMonkey gain by distilling all N
into structured summaries and running a tournament plus one refinement pass?

**Seeds.** `digest`-backed structured rollout summaries (hypotheses, progress,
failure modes — the paper's finding is that these beat raw trajectories as the
comparison substrate); recursive tournament voting over summary groups;
one distill-refine pass seeded with the tournament winner plus the losers'
failure modes; isolation via loop 38's `branches` worktrees; strictly OFF by
default with the cost printed before the run (R-F, and `cost.py`/`budget.py`
already exist).

**Verify probe shape (R-I).** A scripted multi-rollout run where no single
rollout passes the verify command but the refinement pass — given the losers'
failure modes — does; `bestofn.*`/`pdr.*` events show N summaries, the
tournament bracket and the refine step; and a cost probe showing the run
refused to start when N exceeded the configured budget.

### CYCLE R49 — Loop 49: provenance-gated persistence

**Question.** Loops 46 and 47 create the first artifacts that outlive a run.
What is the smallest mechanism that makes it *structurally impossible* for
content CodeMonkey did not trust to author one?

**Seeds.** A taint bit on every `ToolResult` (`web_fetch` bodies, `shell`
stdout, files outside the workspace roots are untrusted by construction);
propagation through the message history so the journal records which turns saw
untrusted content; a hard gate — a skill admission or playbook delta whose
producing turn is tainted is refused, not warned about; the existing
`envquarantine`/`approvals` escalation path for the user to override
deliberately; `redact` and `claims` for the evidence trail. The out-of-band
literature's own finding applies: keep the checker away from the attack
surface, so the gate reads metadata (taint, provenance, probe exit code), never
the untrusted text.

**Verify probe shape (R-I).** A local fixture page containing an injected
"add this to your skills" instruction, fetched by `web_fetch` in a live run:
the run may use the content, and the admission attempt is **refused with the
taint cited** in the journal; the same skill admitted from a clean run
succeeds. Plus a propagation test that taint survives compaction and spill.

### CYCLE R50 — Loop 50: did it actually learn, and v5.0 acceptance

**Question.** Under R-K, does any of 46–49 produce forward transfer on this
repo's own suites — and does the long-horizon regime, where the field's real
gap lives, move at all?

**Seeds.** A CL-style protocol over the existing eval suites: sequential task
order, library-on vs library-off arms, forward transfer and a retention check
on an earlier suite, all under R-H's time-uniform statistic; a long-horizon
suite modeled on SWE-EVO's shape (multi-file, multi-session, test-suite-graded)
run through `sessions`; `build/CAPABILITY_REGISTER.md` updated with the arc's
PROVEN-LIVE / UNIT-ONLY / DEAD verdicts; the v5.0 evidence pack and Gate 7
report to the user, including any charter withdrawn for failing R-K.

**Verify probe shape (R-I).** `codemonkey eval` reports both arms with the
named statistic and a forward-transfer figure; the register has no
UNVALIDATED row; `bash build/acceptance_sweep.sh` green with BLOCKED rows
carrying reasons; and — the one that matters — a written verdict for each of
46, 47, 48 reading KEPT (with its number) or DELETED (with its reason).

---

## §D — Authorization

This file is a **proposal**. Per AGENTS.md, each loop's build cycles are
appended to `build/plan.md` only after that loop's research cycle
(`build/research-loop<N>.md`, ≥5 cited candidates, ranked SELECTED) is written.
Loop 46's research cycle is `build/research-loop46.md`, written with this file;
its selected cycles are appended to `build/plan.md` under
`### loop46: cycles` and are marked NOT AUTHORIZED pending the user's word.

**Ordering constraint.** Loops 38–45 are open. Loop 38's cycles 74–81 are
appended and cycle 74 is in flight with a red suite (`build/critic-cycle74.md`,
fix cycles 74F1–74F6). Nothing in this arc may be built before loop 45's v4.0
acceptance, and the arc's first cycle is blocked on that gate by construction.
