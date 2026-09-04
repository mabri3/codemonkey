# Loop 39 research: failure-anchored recovery (CYCLE R39)

**Date:** 2026-09-04 · **Charter:** `build/loops-38-45-proposal.md` (R39) ·
**Entry condition FULFILLED:** R38 closed (loop38-final, 97404c3).
**Core-design PARTIAL:** a policy that can *terminate* a run is adjacent to
approval semantics — **R39 ENDS BY ASKING** (the stop policy in C91 goes no
further than a proposal until the user approves it).

**Question** (charter): the journal already types every failure
(`error_class`) and nothing reads it *during* a run. Can the first
unrecoverable step be localized online, and does acting on it beat running to
`max_turns`?

## In-repo evidence (this repo, not literature)

- `journal.classify_error` types failures; `class_summary` counts them;
  `journal show <thread>` prints the summary — but only post-hoc. Nothing in
  `loop.py` reads it mid-run.
- `compile_rules` already mines repeat `(tool, error_class)` offline for
  rule drafts — the signal exists; loop 39 moves it online.
- `checkpoints.py` snapshots pre-mutation state per tool call (14F1 groups);
  `restore_latest` exists — rollback machinery, no policy driving it.
- `loop.py` bails at `max_turns` with an error event — no typed report, no
  early stop, no checkpoint pointer.
- `--best-of` (cycle 79) verifies *outcomes*; nothing verifies *trajectory
  health* mid-run. Loop 39 is the trajectory-health counterpart.

## Candidates (≥5, each: name, why, citations)

### C1 — Online failure taxonomy over `error_class`
Map the journal's existing classes onto the published nine-category framing —
goal misinterpretation, wrong tool, wrong argument/target, observation
failure, constraint violation, recovery failure, looping/over-action, unsafe
trust of external content, state contamination (AgentRx nine-category
taxonomy, adopted verbatim by AgentAtlas rather than re-derived:
https://arxiv.org/pdf/2605.20530). Deterministic mapping, no LLM judge:
this repo's observable classes (tool error text, approval denial, transport
error, schema mismatch, empty result, auth) map onto 6 of the 9; the other 3
(goal misinterpretation, unsafe trust, state contamination) are recorded as
unmappable-by-rule with reasons, not guessed. MAST's 14-mode taxonomy over
1600+ traces corroborates the shape (step repetition 17.14% the largest
single mode: https://arxiv.org/abs/2503.13657).
*Why high-leverage:* turns an un.read post-hoc log into a typed signal every
later cycle can condition on; zero model cost.

### C2 — Stuck-loop detector (same failure ×3 = a loop, not progress)
Per-turn check in `loop.py`: the same `(tool, error_class)` three times, or
TraceProbe's search-loop signature (repeated search/read with no new paths —
the most stable corpus-level difficulty clue:
https://arxiv.org/html/2607.06184v1). Emits a structured `stuck` event and a
system nudge; does NOT terminate (termination is C91's ask). The
thought-action-result literature shows failures correlate with "no-influence"
actions (next move ignores the previous result: 6.2% vs 1.2% RepairAgent,
14.6% vs 4.9% AutoCodeRover: https://arxiv.org/pdf/2506.18824) — the detector
also fires when K consecutive tool results change neither the tree nor the
plan (outcome-based stuck, not just error-text stuck).
*Why high-leverage:* cheapest possible intervention (a counter), directly
targets the 17%-class failure mode.

### C3 — Recovery policy table (class → action)
A static table mapping taxonomy class → {retry-differently hint, rollback
suggestion, stop-and-report}, consulted when C2 fires. Hints are injected as
a system reminder naming the failure and the untried alternative (model
still decides — policy advises, never commands, until C91 is approved).
"Recovery failure — agent does not respond appropriately to a prior mistake"
is its own taxonomy category (AgentRx #6): the table's retry-differently row
exists precisely for it. Successful trajectories respond to error signals
92% vs 37% for failed ones ("Failure as a Process":
https://arxiv.org/html/2607.09510v1) — the table operationalizes "respond".
*Why high-leverage:* converts the literature's main behavioral discriminator
into mechanism.

### C4 — Recovery-budget cap (stop rediagnosing, not just retrying)
"Once a recovery exceeds the typical successful length, continuing to repair
rarely helps" (Finding 10, Failure-as-a-Process). Only 18% of failed
trajectories terminate shortly after lock-in; 82% burn the remaining budget
(Finding 7). Cap: after the first error signal, at most M further turns
(config `recovery_budget`, default sized from the repo's own golden-suite
successful-recovery lengths) before the policy forces stop-and-report.
Measured per R-F as turns AND tokens saved vs burning to `max_turns`.
*Why high-leverage:* bounds the worst case mechanically; the 12–82% longer
failure trajectories (Majgaonkar et al., via
https://doi.org/10.48550/arXiv.2604.02547 — with that paper's caveat that
length confounds with difficulty, so the probe compares same-scenario
pre/post, not pooled means).

### C5 — Typed failure report + honest stop (the charter probe)
When the policy says stop (stuck + no untried alternative, or recovery
budget exhausted): end early with `{failure_class, taxonomy, first_stuck_turn,
attempts, checkpoint_id, journal_thread}` printed as `failure_report.*`
events and returned in the run result — "here is where I got stuck, here is
the checkpoint" instead of a confident wrong patch or a silent max_turns
bail. The charter's FIRST probe: scripted failing scenario, pre-loop agent
burns the full budget, post-loop agent stops early with the typed report
(turn count + token cost both, R-F).
*Why high-leverage:* it is the loop's headline; every other candidate serves
it. Termination power is exactly why this research ENDS BY ASKING.

### C6 — Checkpoint-rollback recovery action
On tree-clobber classes with a rollback policy: `restore_latest` the 14F1
group, journal the rollback, continue from the restored tree. Isolation
alternative (worktree per attempt) belongs to loop 41, not here.
*Why high-leverage:* closes the loop from detection to recovery for the most
concrete failure class. Gated: default SUGGEST (report names the checkpoint),
AUTO only if the user approves the policy in the R39 ask.

### C7 — Validation-effort floor (rejected — see below)
Successful agents validate 35–37% of steps vs 12–19% for weak ones; delaying
the first edit predicts success (ρ=+0.68:
https://doi.org/10.48550/arXiv.2604.02547). A floor (force a validation tool
call every K turns) is tempting but it dictates run *shape*, not failure
*response* — loop 40's territory (test loop as control signal), not 39's.

## SELECTED (ranked)

1. **C1 taxonomy** → C88: `failclass.py` mapping + `journal show` taxonomy
   rows. Foundation; everything else keys off its labels.
2. **C2 stuck detector** → C89: online counter in `loop.py`, `stuck` event +
   nudge, no termination.
3. **C5 typed report + honest stop** → C90/C91: the policy table (C3 merged
   in — a table with one consumer cycle is over-modular; the table ships
   with its first consumer) + budget cap (C4 merged in — same reason) +
   stop-and-report. PROPOSED ONLY until the user approves termination in
   the R39 ask; C90 builds the report machinery (no termination: report is
   *emitted* at max_turns bail alongside the early-stop check in dry-run
   form?), C91 wires the actual early stop behind approval.
   
   Cleaner split honoring "ends by asking": C90 = report machinery +
   policy table + budget cap, all wired EXCEPT the terminate call, with a
   `--dry-run`-style `recovery: report-only` default; probe asserts the
   report would-have-stopped at turn T (event present, run still completes).
   C91 = flip to enforced stop (early exit + typed report), BLOCKED on user
   approval of the termination policy. C91 is appended but marked
   AWAITING-ASK.
4. **C6 rollback** → C92: policy-gated rollback (default SUGGEST), probe =
   scripted clobber → rollback → verified content. Also awaits the ask
   (it mutates run outcome). Appended after C91.

**Rejected with reasons:** C7 (belongs to loop 40, recorded above);
LLM-as-judge failure classification (recurring cost per turn, uncalibrated
labels — the deterministic mapping covers the observable classes; the 3
unmappable categories stay honestly unmapped); trajectory-length cutoff as
*the* stop signal (the 2604.02547 reversal shows length confounds with
difficulty — length is an input to the budget cap, never the verdict).

## Cost note (R-F, charged against the loop that spends it)

Research proper: this file + web searches (≈20 tool calls, no model
inference). Build cycles carry their own turn/token accounting per the
charter probe (pre vs post turn count + token cost, printed in the probe).

## Appended cycles

`loop39:` C88–C92 + `loop39-final`, appended unchecked to `build/plan.md`.
Numbering note: 82–87 are reserved by the already-appended (unauthorized)
loop-46 arc; loop-39 build cycles continue at 88. C91/C92 are marked
AWAITING-ASK (termination/mutation policy) and no worker starts them until
the user approves in the R39 ask — the authorization for loops 38–45 covers
research + report-only machinery, not autonomous termination.
