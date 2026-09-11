# Loop 50 research — did it actually learn? + v5.0 acceptance (CYCLE R50)

**Date:** 2026-09-11 · **Charter:** `build/loops-46-50-proposal.md` §CYCLE R50
(:206–224) · **Entry condition: FULFILLED** — loop 49 closed at `8203d76`
(C117–C120, suite 935/5). Arc authorized 2026-09-10, ordering waived.
**Core-design: NO** — measurement over existing harnesses + a release
close; acceptance terms below, no ask.

## Published context, UP FRONT (R-G)

- **SWE-EVO (Benchmarking Coding Agents in Long-Horizon Software Evolution
  Scenarios,** https://arxiv.org/abs/2512.18470 **):** 48 tasks built from
  release notes of seven mature Python projects, **average 21 files** per
  task, test suites averaging **874 tests**; GPT-5.4 with OpenHands scores
  **25%** on SWE-EVO vs **72.80%** on SWE-bench Verified — the field's own
  measure of the long-horizon gap. Proposes **Fix Rate** for partial
  progress on multi-step tasks. **Never a target** — different repos,
  different models; the portable parts are the SHAPE (multi-file,
  multi-session, test-graded) and the Fix-Rate idea.
- **SWE-Bench-CL (** https://arxiv.org/pdf/2507.00014 **, carried from R46):**
  continual-learning framing for coding agents: **stability** (retention on
  old tasks) vs **plasticity** (forward transfer on new ones), scored by
  **CL-F1** — the exact trade-off loop 46's R-K states in words.
- **R-H (this repo's own rule):** verdicts on measured rates need a
  **time-uniform** statistic, and an unmeasurable rate is named, never
  filled in. The harness ships `certify.hoeffding_gate` (kind
  `hoeffding-gate`) — the named statistic the arms already print.

## In-repo grounding (re-verified at `8203d76`)

- `skills_arms.py` (C87, extended C112): `--arms skills-on,skills-off` and
  `playbook-on,playbook-off`; forward transfer + retention on an earlier
  suite; the named statistic; contamination over BOTH stores; BLOCKED
  discipline (`None`, never 0) — the CL harness's skeleton already exists.
- `eval.run_suite` supports `early_stop` over the same Hoeffding gate.
- Suites: `build/suites/{trivial,rubric}.yaml` — single-task-shape files.
- `sessions` (jsonl/sqlite stores) + `exec resume` — the multi-session
  machinery a long-horizon suite needs; nothing today drives a suite
  through sessions.
- The arc's artifacts to judge: skills (loop 46), playbook (47, incl. the
  lessons consolidation), bestofn refine/tournament + cost gate (48),
  taint/provenance gates (49) — each with probe transcripts in the register.

## Candidates (each: name, why, citations, attachment, R-I probe)

### C1 — The CL protocol over the existing arms (sequential, both surfaces)
A runner that executes a suite IN ORDER per arm (library-on vs library-off),
with a transfer suite (new tasks) and a retention suite (earlier tasks),
reporting forward-transfer and retention both under the named gate — the
SWE-Bench-CL protocol at this repo's scale, on ONE command:
`codemonkey eval <suite> --arms <surface>-on,<surface>-off --cl-protocol
--retention <earlier-suite>` (extends `skills_arms`, does not fork it).
**R-I probe (offline):** scripted exec through the real path → both arms,
the named statistic, transfer + retention figures with BLOCKED discipline
when the endpoint is down; sequential order asserted on the trace.

### C2 — The long-horizon suite: SWE-EVO's SHAPE at repo scale
`build/suites/long-horizon.yaml`: tasks that (a) span multiple steps in one
session, (b) REQUIRE a previous task's artifact to start (task N+1 reads
what N wrote — the persistence dimension via the workspace, resumed session
support where the runner needs it), and (c) are graded by the machine
checks the suite format already has. Run through the existing exec path;
the suite is the fixture, and its SHAPE (multi-step, order-dependent,
machine-graded) is what the field's gap is about.
**R-I probe:** the suite runs to completion through the real path offline
(scripted provider where needed); order-dependence proven by running task
N+1 FIRST in a scratch workspace → it fails its precondition check (the
discriminating control).

### C3 — Fix Rate: partial progress, honestly
The Fix-Rate analogue: for a task with K checks, record the fraction
passed (the suite's per-task check results already exist) and report
`fix_rate` alongside `pass_rate`; a task that passes 3 of 4 checks is 0.75
fix-rate and 0 pass-rate. No target number; the metric is local and named.
**R-I probe:** a task fixture that passes 2 of 3 checks → `fix_rate 0.667,
pass_rate 0` on the trace; a fully passing task → 1.0/1.0.

### C4 — The verdicts + v5.0 close (the deliverable the whole arc owes)
A written verdict per loop 46/47/48/49 reading **KEPT** (with its number —
or its named mechanism + UNMEASURED-WITH-DATE rate) or **DELETED** (with
its reason); v5.0 evidence pack over the arc; version bump; sweep; tag;
Gate 7 report. This is a RELEASE act with terms, not a design decision.
**R-I probe:** `codemonkey --version` → 5.0.0; the sweep green with BLOCKED
rows carrying reasons; the register with no UNVALIDATED row; the report
carrying the four verdicts; tag `v5.0.0` on the pushed commit.

### C5 — REJECTED: flip the verdicts on mechanism alone *as if* measured
R-K/R-H forbid presenting a mechanism as a measured rate. The verdicts
KEEP mechanisms that are PROVEN-LIVE and NAME their missing rates; no
sentence in the v5.0 report may read as a field number that was not run.
**REJECTED: deleting a surface for an unmeasurable rate** — R-A deletion
triggers on a measured near-zero over an observable population; with the
endpoint down, no such population exists (unmeasurable establishes neither
presence nor absence).

## SELECTED (ranked)

1. **C1** — the CL protocol runner (transfer + retention under the gate).
2. **C2** — the long-horizon suite by shape.
3. **C3** — Fix Rate reporting.
4. **C4** — the verdicts + v5.0 close.

## The verdict matrix this loop must fill (from the arc's own records)

| loop | surface | status entering R50 | verdict shape at close |
|---|---|---|---|
| 46 | skills (quarantine/gate/taint/revoke) | PROVEN-LIVE; transfer number UNMEASURED-WITH-DATE | KEPT (mechanism); rate named missing |
| 47 | playbook (delta merge/injection/consolidation) | PROVEN-LIVE; live rate unmeasured | KEPT (mechanism); rate named missing |
| 48 | bestofn refine/tournament/cost gate | PROVEN-LIVE; refine-vs-none delta unmeasured | KEPT (mechanism); rate named missing |
| 49 | provenance-gated persistence | PROVEN-LIVE; live injection firing unmeasured | KEPT (mechanism); firing named missing |

## Cost note (R-F, charged against the loop that spends it)

The CL run costs what the arms cost (N tasks × 2 arms × per-task cost,
inside declared budgets; the cost gate's machinery from C115 applies);
offline probes and tests are scripted: zero tokens. Fix Rate is free
(checks already recorded).

## ACCEPTANCE (loop 50, core-design NO — terms, not an ask)

`codemonkey eval` reports both arms with the named statistic and a
forward-transfer figure (BLOCKED-with-reason while the endpoint refuses);
the long-horizon suite runs offline with its order-dependence control; Fix
Rate prints beside pass rate; the register has no UNVALIDATED row; the
sweep is green with every BLOCKED row carrying its reason; and — the one
that matters — **a written verdict for each of 46, 47, 48 (and 49) reading
KEPT (with its number, or its mechanism + named missing rate) or DELETED
(with its reason)**. v5.0: version bumped, evidence pack cut, THREAT_MODEL
and BUILD_REPORT updated, tag `v5.0.0`, Gate 7 handoff to the operator.
