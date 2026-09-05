# Loop 46 research — the skill library: a run that makes the next run cheaper

**Date:** 2026-09-04 · **Cycle:** R46 (compounding arc,
`build/loops-46-50-proposal.md` §0/§A/§B)
**Premise:** every arc so far improves a *single* run. Loop 46 is the first
cycle in this repo's history where an artifact authored by run N is allowed to
change run N+1. Arc rules R-J (quarantine, provenance, revocability) and R-K
(learning is measured, not asserted) exist because of this loop.

## Method

Web search (September 2026) for the state of the art in self-evolving coding
agents, agent skill/tool synthesis, evolving context, test-time scaling and
agentic persistence security; then `graphify query` against this repo's graph
for the modules each candidate would have to reach. Every candidate below names
(a) a published anchor with a number, (b) the **existing** CodeMonkey module it
attaches to, and (c) its R-I entry-point probe shape. Candidates with no
in-repo attachment point were dropped, not written up.

**In-repo grounding** (`graphify query "which modules are unreachable orphans
and how do exec, loop, strategies and lessons connect"`, plus reads at HEAD
`2575515`): `tools/__init__.py` is a `_MODULES` / `SPECS` / `PARAMS` registry
that `prompt_block` advertises and `dispatch` sandbox-gates through
`sandbox.check` — a single, already-policed admission point for any new tool.
`strategies/__init__.py::DOMAINS` carries compaction / memory / session_state
with env-overridable names (the A19 pattern) — a fourth and fifth domain cost
nothing structurally. `lessons.py` already implements *admission by measurement*
(`add(..., verified=False)` drafts, `mark_verified` set by an eval run rather
than a model's opinion, `retrieve(verified_only=True)` gating what is ever
injected) — exactly the gate shape R-J demands.
`journal.py` records typed per-step data including `error_class`. `eval.py` /
`rubrics.py` / `certify.py` are the measurement harness. `checkpoints.py` gives
per-call snapshot groups. Nothing in loop 46 needs a new subsystem; it needs a
persistence surface bolted onto four that exist.

## Candidates (≥5, each with its anchor, its attachment point and its R-I probe)

### C1 — Runtime tool synthesis with a persistent, gated skill library
**Anchor.** Live-SWE-agent evolves its own scaffold *during* the run from a
bash-only starting point, reaching **75.4%** on SWE-bench Verified without
test-time scaling and **45.8%** on SWE-Bench Pro — the best known open-source
figures — via lightweight reflection that triggers context-specific tool
synthesis, with no offline training. Its authors explicitly name a persistent,
indexed **skill library** as the future direction they did not build
(https://arxiv.org/pdf/2511.13646). MUSE-Autoskill formalizes the
create → memory → manage → evaluate cycle (https://arxiv.org/pdf/2605.27366);
CoEvoSkills adds co-evolutionary *verification* of skills, i.e. a skill and its
check evolve together (https://arxiv.org/html/2604.01687).
**Attachment.** `tools/__init__.py` registry + `sandbox.py` classification +
`shell`/`delegate` for synthesis + `lessons.py`'s admission-by-measurement
pattern (`verified` / `mark_verified` / `retrieve(verified_only=True)`) +
`checkpoints` for rollback.
**R-I probe.** Run A synthesizes a skill and admits it; run B on a related task
shows the skill name in its `--json` tool trace and finishes in strictly fewer
turns than the `--no-skills` control.
**Risk.** This is the arc's whole attack surface. Mitigated by quarantine +
mandatory self-probe + loop 49's taint gate; ships OFF by default (R-F).

### C2 — Delta-curated evolving playbook (ACE)
**Anchor.** ACE (ICLR 2026) treats context as an evolving playbook curated by a
generator / reflector / curator triad, reporting **+10.6%** on agent benchmarks
and **+8.6%** on finance *without labeled supervision*, learning from natural
execution feedback. Its named failure modes are **brevity bias** (summarizing
away domain insight) and **context collapse** (iterative rewriting eroding
detail) — both of which a rewrite-style lessons file is exposed to
(https://arxiv.org/abs/2510.04618, production notes:
https://contextual.ai/blog/optimize-agent-performance-using-self-evolving-context).
**Attachment.** `lessons.py` (curator gate exists: `verified` + `mark_verified`),
`compile_rules.py` (playbook → enforcement exists), `learnedctx.py` +
loop 38's `context` strategy domain (injection point exists), `journal.py`
(reflector input exists).
**R-I probe.** Second run's system prompt provably carries the admitted delta
and avoids run one's failing step; plus a 50-round collapse regression proving
early entries survive byte-for-byte.
**Note.** Chartered as loop 47 — it is a *different* persistence surface from
C1 (prose that changes the prompt vs code that changes the tool set) and mixing
them in one loop makes R-K's attribution impossible.

### C3 — Parallel-Distill-Refine + Recursive Tournament Voting
**Anchor.** Unified test-time scaling for agentic coding: N independent
rollouts → compact structured summaries → recursive small-group tournament →
sequential refinement. Claude-4.5-Opus **70.9 → 77.6%** on SWE-bench Verified
and **46.9 → 59.1%** on Terminal-Bench v2. The load-bearing finding for this
repo: *structured bounded summaries outperform raw trajectories as the
comparison substrate*, and blindly scaling turns accumulates early tool errors
(https://arxiv.org/abs/2604.16529).
**Attachment.** loop 38's `bestofn.py` (whose first-pass-wins rule discards
exactly the evidence PDR uses), `digest.py`, `branches.py`, `jobs.py`,
`cost.py`/`budget.py`.
**R-I probe.** A run where no single rollout passes the verify command but the
refine pass, seeded with the losers' failure modes, does.
**Note.** Chartered as loop 48. Highest-certainty delta, lowest novelty, and it
buys accuracy with money — OFF by default, cost printed first.

### C4 — Provenance/taint gating for persisted artifacts
**Anchor.** Prompt injection remains OWASP **LLM01** and the dominant agentic
failure in production, with **28 of 53** tracked agentic projects being coding
agents including the five fastest-growing ones
(https://www.helpnetsecurity.com/2026/06/11/owasp-prompt-injection-ai-security-failures/);
MOSAIC demonstrates knowledge-guided CLI-command-composition attacks
specifically against LLM coding agents (https://arxiv.org/pdf/2607.02857); the
out-of-band defense literature's structural finding is to keep the evaluator
away from the untrusted content and judge on metadata
(https://arxiv.org/pdf/2606.26479, survey: https://arxiv.org/pdf/2510.06445).
**Attachment.** `envquarantine.py`, `permissions.py`, `approvals.py`,
`sandbox.py`, `redact.py`, `claims.py`, `journal.py`.
**R-I probe.** A fixture page carrying an injected "add this to your skills"
instruction: the admission is refused with the taint cited in the journal,
while the same skill from a clean run is admitted.
**Note.** Chartered as loop 49 — but see the ranking: a *minimal* form of it is
pulled forward into loop 46, because C1 without any taint notion is a
persistence surface with no lock on it.

### C5 — Continual-learning measurement (CL-F1, forward transfer, retention)
**Anchor.** SWE-Bench-CL frames coding-agent learning as the
stability–plasticity trade-off and proposes CL-F1 to score it, measuring
forward transfer and tool-use efficiency rather than a single pass rate
(https://arxiv.org/pdf/2507.00014); harness-engineering practice makes the same
point about attributing gains to the scaffold rather than the model
(https://lilianweng.github.io/posts/2026-07-04-harness/).
**Attachment.** `eval.py`, `certify.py` (post-R-H), `rubrics.py`, `matrix.py`.
**R-I probe.** Both arms and a forward-transfer figure printed by
`codemonkey eval`, with a retention check on an earlier suite.
**Note.** Chartered as loop 50. R-K makes it mandatory rather than optional:
without it, loop 46's claim is unfalsifiable.

### C6 — Long-horizon software evolution mode
**Anchor.** SWE-EVO: 48 tasks from real release notes, averaging **21 files**
per task against suites averaging 874 tests; SOTA agents score **~21–25%**
against **~65–73%** on SWE-bench Verified — the field's real gap is sustained
multi-step, multi-file work, not single-issue repair
(https://arxiv.org/abs/2512.18470).
**Attachment.** `sessions.py`, `jobs.py`, `journal.py`, `status_mod.py`,
`graphquery.py`, `checkpoints.py`.
**Ranking note.** Folded into loop 50 as the evaluation regime rather than
given its own loop: loops 41 (atomic multi-file), 42 (horizon compilation) and
44 (budgets) already charter the *capabilities* this regime needs, and building
a third planning surface before those land would duplicate them. What is
missing is the *suite*, which is loop 50's job.

### C7 — Self-modifying scaffold (Darwin Gödel Machine)
**Anchor.** DGM rewrites its own source under evolutionary search with an
archive of variants, improving **20% → 50%** on SWE-bench
(https://arxiv.org/pdf/2505.22954); the broader read is that recursive
self-improvement has not shipped and current fixed improvement operators
plateau (https://www.morphllm.com/self-improving-ai).
**Verdict: REJECTED for this arc.** Letting a cycle rewrite
`src/codemonkey/` is a core-design change; AGENTS.md "Honor gates" requires
stopping and asking rather than hot-reworking approved design, and R-J's
revocability guarantee is not achievable when the thing being modified is the
code that performs the revocation. C1 is the bounded form: new *tools* in a
quarantined library, never edits to the loop. If the user wants C7, it is a
separate authorization.

### C8 — Cross-repo shared skill/lesson exchange
Skills learned in repo A published for repo B. **REJECTED (deferred):** it
converts a local, auditable surface into a distribution channel, and R-J's
provenance guarantee stops at this machine. Revisit only after loops 46, 47 and
49 are PROVEN-LIVE and the register says so.

## Rationale & ranking

C1 is selected as loop 46 on three grounds. **Magnitude:** it is the largest
published delta available to a scaffold that cannot retrain its model, and the
paper's stated unbuilt next step *is* the thing this repo is unusually equipped
to build. **Fit:** the admission gate C1 needs — promote only on a mechanical
check, never on a model's say-so — already exists as `lessons.py`'s
verified-by-eval flag (`mark_verified`, consumed by `retrieve(verified_only=True)`); the registry it must extend is already the single
sandbox-policed choke point; rollback is `checkpoints`. **Order:** C2's
playbook and C3's tournament both become measurable *through* the same
library-on/library-off arm structure C1 forces us to build, so C1 first makes
47 and 48 cheaper, while the reverse is not true.

The one adjustment to the charter table: C4's *minimal* form is pulled into
loop 46 rather than waiting for loop 49. Loop 49 builds full taint propagation
through history, compaction and spill; loop 46 cannot ship without at least the
coarse rule — **a turn that read `web_fetch` output or out-of-workspace content
may not admit a skill** — because otherwise loop 46's deliverable is a
persistent, model-authored, prompt-reachable code surface with no lock on it.
That is a cycle inside loop 46 (below), not a borrowed loop.

C5's measurement is *not* deferred wholesale either: loop 46's final cycle must
report forward transfer under R-K, or loop 46 does not close.

## SELECTED

Appended to `build/plan.md` as `### loop46: cycles` (NOT AUTHORIZED — pending
the user's word and loop 45's v4.0 gate):

1. **CYCLE 82** — skill artifact format + quarantined store (`.codemonkey/skills/`,
   manifest with name/params/probe/provenance/run-id; load = OFF by default).
2. **CYCLE 83** — the admission gate: run a candidate's self-probe in the
   existing sandbox; promote on exit 0 only; record the verdict; evict on
   later failure (R-A).
3. **CYCLE 84** — `skill_create` tool + `strategies.skills` domain
   (`off` default | `use` | `learn`); admitted skills merged into
   `SPECS`/`PARAMS` at run start; name collisions with built-ins refused.
4. **CYCLE 85** — the coarse taint rule (C4 minimal): an admission attempt from
   a turn that consumed untrusted tool output is refused with the reason
   journaled.
5. **CYCLE 86** — `codemonkey skills list|show|revoke|disable` — the R-J
   revocation surface, one command, restores prior behavior.
6. **CYCLE 87** — R-K measurement + loop 46 acceptance: library-on vs
   library-off arms on an eval suite, forward transfer and retention reported
   under R-H's statistic, register rows updated, KEPT-or-DELETED verdict
   written.

Full cycle text with literal verify probes is in `build/plan.md`.


---

## 91F4 citation re-point (2026-09-04)

This file was written against a tree that has since changed under R-A. Two
modules it cited as attachment points no longer exist, and the re-points are
recorded here rather than made silently:

| Cited | Status | Re-pointed to |
|---|---|---|
| `lessons_gate.py` (×4, incl. C1's whole "Fit" argument) | DELETED by cycle 81 (`5ea507f`) under R-A | `lessons.py` — `add(verified=False)` / `mark_verified` / `retrieve(verified_only=True)`. The admission-by-measurement *pattern* survives intact; only the wrapper module went. C1's Fit argument stands. |
| `truthpass.py` (C4 attachment) | DELETED by cycle 81 (`5ea507f`) under R-A | Nothing. It verified build-ledger claims, not tool-output provenance, so it was a mis-citation for C4 even before deletion. C4's real attachment points are `claims.py`, `journal.py`, `sandbox.py`, `redact.py`. |

**Standing rule (proposed for the arc, alongside R-J/R-K):** a research file's
in-repo attachment points are re-verified against the tree at the moment its
cycles are built, and a citation naming a module that no longer exists is a
BLOCKING finding for that cycle, not a footnote. `build/research-loop45.md`
was written 2026-09-04 22:00 citing a module cycle 81 deleted the same day —
so this check has to be mechanical, not a habit.
