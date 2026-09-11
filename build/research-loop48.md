# Loop 48 research — parallel-distill-refine + tournament voting: `--best-of`'s correct form (CYCLE R48)

**Date:** 2026-09-11 · **Charter:** `build/research-loop46.md` §C3 (chartered
here) + `build/loop48-research` slot in `build/plan.md` · **Entry condition:
FULFILLED** — loop 47 closed at `9a3657f` (C107–C112, suite 903/5; playbook
PROVEN-LIVE, its live number named). Arc authorized 2026-09-10, ordering
waived. **Core-design: NO** — `--best-of` is an existing opt-in surface
(loop 38, cycle 79) and this loop extends it; acceptance terms below, no ask.

## Published context, UP FRONT (R-G)

- **PDR (parallel-distill-refine; chartered for this loop in R46,**
  https://arxiv.org/abs/2604.16529**):** N independent rollouts → compact
  structured summaries → recursive small-group selection → sequential
  refinement. Claude-4.5-Opus **70.9 → 77.6%** SWE-bench Verified and
  **46.9 → 59.1%** Terminal-Bench v2. Load-bearing findings: *structured
  bounded summaries outperform raw trajectories as the comparison substrate*,
  and *blindly scaling turns accumulates early tool errors*. **Never a
  target** — those are frontier-model numbers on other harnesses; this loop
  takes the mechanism, not the figure.
- **Compute-optimal test-time scaling (Snell et al., ICLR 2025,**
  https://arxiv.org/abs/2408.03314**):** adaptive allocation beats a
  best-of-N baseline by **>4× in compute efficiency**; *easy* prompts favor
  sequential revision, *hard* prompts favor parallel sampling + search —
  and on the hardest problems test-time compute barely helps at all (a
  reason to keep spending OPT-IN and printed, not default-on).
- **Juries beat a single judge (PoLL,**
  https://arxiv.org/abs/2404.18796**):** a panel of smaller evaluators beats
  one large judge on human agreement at **>7× less cost**, with reduced
  intra-model bias — the standing argument for a *tournament/panel* selector
  wherever a single verdict would otherwise decide.
- **Parallel-R1 (** https://arxiv.org/abs/2509.07980 **)**: teaching
  parallel thinking via RL — training-time; this repo's executor is frozen
  (no weight updates, ever), so the mechanism is recorded and DEFERRED,
  not adopted.
- **Carried from R46 (in-repo research, cited there):** the R-Q refinement
  note and the "structured summaries as substrate" finding already anchor
  loop 48's direction; this file re-verifies the attachments against the
  tree at `9a3657f` (R-L).

## In-repo grounding (re-verified at `9a3657f`)

`bestofn.py` (R32) today: N candidates, **first verifier-pass wins**, honest
failure with the last failing tail when none pass, zero-residue workspace
snapshot between attempts (cycle 79), **default OFF** (`--best-of` default 1;
`--best-of N>1` requires `--verify-command` — `exec.py:681` raises without
one). Wiring: `cli.py:794–800` (`--best-of`, `--verify-command`),
`exec.py:662–681` (`_run_once` per candidate). Neighbours that already exist:
`digest.py` (bounded run digest — the summary shape C1 needs), `cost.py` /
`budget.py` / `budgets.py` (cost accounting + declared budgets), `branches.py`
(worktree isolation if candidates ever need real isolation instead of
snapshot-reset). Nothing in `bestofn.py` consumes a LOSING candidate's
evidence today — that is the gap this loop closes.

## Candidates (each: name, why, citations, attachment, R-I probe)

### C1 — The refine pass: losers' evidence seeds a sequential attempt
When every candidate fails the verifier, the run does not end with "last
tail": the failure evidence (per-candidate verifier tails, the bounded
summaries) seeds ONE refine attempt (sequential), which is verified by the
same machine check. Parallel-then-sequential is exactly Snell's two axes;
the losers' failure modes are the information bestofn currently discards.
**Attachment:** `bestofn.py` + `exec.py` best-of path; `digest.py` for
summaries.
**R-I probe:** a scripted run where NO candidate passes but the seeded refine
does — `bestofn.refine` event shows candidates=N, refined=1, verified=True.

### C2 — The selector, in two tiers: verifier first, tournament on abstain
Tier 1 is the existing machine verifier (unchanged — the model never
self-reports). Tier 2, ONLY when no verifier verdict is available (no
`--verify-command` and no `verify_command` config): a deterministic
**pairwise tournament over the candidates' structured summaries** — each
pair compared by a bounded, scripted comparison the operator supplies (this
repo never asks the model to grade itself; a tournament without a judge
degrades to "report all candidates" — the honest empty). *Note the
deliberate scope cut:* PoLL's panel-of-models is not portable to a
single-endpoint repo; the tournament here is a STRUCTURE the harness can
execute, and its verdict is only claimed when a comparison function actually
ran.
**Attachment:** `bestofn.py` (`select_by_tournament(candidates, compare_fn)`
— pure; `compare_fn` injected).
**R-I probe:** in-process: 4 candidates, a scripted `compare_fn` → the
winner is deterministic across runs; with no `compare_fn`, the result is
`{"selected": None, "reason": "no comparison provided"}` — never a model
guess.

### C3 — The cost gate: printed BEFORE the run, enforced at the boundary
R-F hardens loop 38's default-OFF: `--best-of N` must print the projected
cost (N × the first-candidate token/wall figures from the CURRENT run's
history when available, else N × the declared per-run budget caps) BEFORE
the extra attempts are spent, and refuse to exceed the declared budgets
(existing `budgets.py` machinery — a limit that is only reported is not a
limit). Cite Snell: the budget is the interface; cite R-F: OFF by default.
**Attachment:** `exec.py` best-of path + `budgets.py` + `cost.py`.
**R-I probe:** `--best-of 3 --budget-tokens <small>` → the projected-cost line
prints, and the run REFUSES (exit 4, `budget.exhausted`) BEFORE candidate 2's
provider call — proven by provider-call count (the C103 boundary pattern).

### C4 — Summaries, not trajectories, as the substrate
The refine seed and the tournament compare SUMMARIES (bounded, structured —
`digest.py` shape + failure tails), never raw transcripts: the PDR finding,
and it keeps worst-case prompt growth bounded. Recorded as a design rule for
C1/C2 rather than a separate cycle; the regression: a 50-candidate run's
refine prompt grows with CANDIDATES, not with transcript size (byte-budget
line printed).

### C5 — REJECTED (this arc): default-on / unattended scaling
Multi-round automatic scaling beyond the declared budget, or making
`--best-of`'s default > 1, is exactly R-F's prohibition: it buys accuracy
with money the operator did not offer this run. Snell's plateau on hard
problems and PDR's "scaling turns accumulates early errors" both argue
against it independently.

### C6 — DEFERRED: RL-trained parallel thinking (Parallel-R1)
Training-time method; this repo's executor is frozen. Recorded (above), not
adopted; revisit condition: never for this repo, per the frozen-executor
invariant.

## SELECTED (ranked)

1. **C1 + C4** — the refine pass seeded by losers' bounded summaries (the
   loop's core mechanism).
2. **C2** — the tournament selector as an OFFLINE, injected-compare structure
   for the no-verifier case (honest empty without a comparison function).
3. **C3** — the cost gate hardened (printed-first + enforced at the
   boundary).

## What `bestofn` KEEPS vs REPLACES (explicit, per the cycle's verify)

**KEEPS:** the `--best-of N` / `--verify-command` surface and its exit
semantics; **first-pass-wins** as the fast path (candidate 1 passing costs
nothing extra); the zero-residue workspace reset between attempts; **default
OFF** (R-F); and the machine verifier as tier-1 judge — the model's
self-report is never a verdict.

**REPLACES:** (a) "verifier fails → return last candidate + tail" becomes
"verifier fails → ONE seeded refine attempt, then verdict"; (b) opaque
candidate text in the failure path becomes bounded structured summaries
(C4); (c) the no-verifier case stops being a usage error door and gains the
injected-compare tournament (and stays an honest empty without one).

## Cost note (R-F, charged against the loop that spends it)

Extra spend = (N − 1) × candidate cost + at most 1 refine cost, all inside
the declared budgets; the projection prints before spending and the refusal
is enforced at the boundary. Offline probes and tests use scripted providers:
zero tokens.

## ACCEPTANCE (loop 48, core-design NO — terms, not an ask)

The refine pass fires only when all candidates fail and is verifiable at the
same machine check (probe shows candidates=N, refined=1, verified=True);
the tournament is deterministic, injected, and honestly empty without a
comparison; the cost line prints before extra spend and a tiny declared
budget refuses with `budget.exhausted` before the crossing call (provider-
call count); `--best-of 1` and the first-pass path are byte-identical to
today; suite green; report section committed. The live accuracy delta of
refine-vs-none remains **UNMEASURED-WITH-DATE** with the endpoint down (same
BLOCKED discipline; arms-style hook named).
