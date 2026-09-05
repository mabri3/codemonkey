# Loop 41 research: repository-scale change that lands or rolls back whole (CYCLE R41)

**Date:** 2026-09-05 · **Charter:** `build/loops-38-45-proposal.md` (R41) ·
**Entry condition FULFILLED:** R38 closed (graph + worktrees reachable),
R39 closed (rollback has a failure signal to trigger on).
**Core-design YES:** this changes how edits are applied and what `undo`
means — **R41 ENDS BY ASKING.**

**Question** (charter): multi-file changes are where an agent quietly
corrupts a repo — one hunk lands, its sibling does not, tests pass by
accident. Structural grounding is reported to cut multi-file patches by
~81% (charter-stated; treat as a claim to reproduce, not a fact). Can a
change be planned as one unit — impact-analyzed against the graph, applied
atomically, rolled back whole on failure — and does that reduce
partial-application?

**Published numbers, UP FRONT (R-G):** no single agreed metric exists for
"partial-application rate"; the comparables are neighboring results, all on
larger models and different harnesses: repository-level repair over graph
representations (ARISE, https://arxiv.org/html/2605.03117),
large-scale multilingual refactoring as a benchmark (SWE-Bench ProMax,
https://arxiv.org/abs/2608.09802), architecture-aware generation for
repo-level feature addition (https://arxiv.org/pdf/2603.01814). Loop-41
probes report OUR partial-application count before/after NEXT TO these —
never as a chase.

## In-repo evidence (this repo, not literature)

- Per-call checkpoints exist (14F1 checkpoint *group*); `undo` reverses the
  last file operation, not a plan. A mid-plan failure leaves a half-applied
  tree with no object recording what the plan was.
- `graphquery` (loop 28) knows callers; `search` guesses them. Signature
  changes today touch what the model thought to grep for.
- Worktrees (loop 31) exist as branch isolation but are never used as a
  plan-execution boundary.
- No counter exists for partial-application: the failure mode has never
  been counted, so no loop can claim to reduce it yet.

## Candidates (each: name, why, citations)

### C1 — Change plan as an explicit object
Files, hunks, order, dependencies between hunks — one JSON object the run
holds BEFORE the first edit, instead of a stream of `edit_file` calls.
Why: a plan can be impact-analyzed, previewed (`diffpreview`, R23B),
approved, and rolled back; a stream can only be regretted. (SWE-Bench
ProMax frames multi-file refactoring as the unit of work:
https://arxiv.org/abs/2608.09802.)

### C2 — Impact analysis over the loop-28 graph
A signature change queries `graphquery` for callers/def sites; the plan
includes them or states why not. Why: the graph knows; `search` guesses —
the charter probe (graph plan touches callers a search plan misses, both
counts reported) is directly this. (ARISE: repo-level graph for fault
localization + repair: https://arxiv.org/html/2605.03117.)

### C3 — Atomic apply on the 14F1 checkpoint group
Extend the per-call group to a whole plan: apply all hunks, run the
verifier; on failure restore every file to pre-plan bytes. Why: reuses
proven machinery (checkpoints + C93 verify gate) instead of inventing
transactions. Byte-identical restore is the charter probe
(`git status` clean, `git diff` empty).

### C4 — Worktree as the isolation boundary
Risky plans apply inside a loop-31 worktree; the working tree only sees
the plan after it verifies. Why: the strongest isolation already in the
repo, and a failed plan leaves literally zero trace in the user's tree.
Cost: worktree setup per plan (measured per R-F).

### C5 — Partial-application counter (measure before/after)
Instrument the current streamer: every multi-file run records
hunks-planned vs hunks-landed vs verifier outcome. Why: without a baseline
count, C1–C4 cannot claim improvement; this is the R-G local number the
loop reports next to the literature.

### C6 — `undo` reverses the plan, not the last file (REJECTED — see ask)
Semantically right, but it redefines a shipped command's meaning for every
existing user and script. Rejected as a default; proposed as the ASK:
ship plan-scoped undo only with explicit approval, otherwise `undo` keeps
file semantics and plan-rollback lives under a new verb.

## SELECTED (ranked)

1. **C5 first** — count the failure mode before touching application
   semantics. No baseline, no claim.
2. **C1 + C3** — plan object with atomic apply on the checkpoint group;
   the mid-plan-failure probe is the acceptance.
3. **C2** — graph-grounded caller coverage, both counts reported.
4. **C4** — worktree boundary for plans flagged risky (opt-in per plan).
5. **C6** — only as far as approved in the ask.

## Cost note (R-F, charged against the loop that spends it)

Graph queries + checkpoint copies per plan are small beside model tokens;
worktree plans pay setup + a full second-tree verify run. All reported
per-plan in the probes.

## ASK (R41 ends by asking — core-design YES)

1. Authorize changing how edits are applied (plan object + atomic
   apply/rollback, C1+C3)?
2. Authorize C6 — `undo` reversing the whole plan — or keep file semantics
   with plan-rollback under a new verb?
3. Authorize C4 worktree-boundary plans (second tree + second verify run
   per risky plan, cost reported)?

## R-L correction (2026-09-05, CYCLE C98) — ⚠️ WITHDRAWN, see below

> C2's premise ("the graph knows [callers]; `search` guesses") does not hold
> for freshly extracted graphs on this extractor (graphify, measured live):
> `calls` edges resolve SAME-FILE calls only — all 1,119 resolvable `calls`
> edges in this repo are same-file, zero cross-file; a 4-file fixture
> (direct + aliased + dynamic dispatch callers) extracts ZERO `calls` edges.
> What the graph does provide cross-file: `imports` / `imports_from` with
> binding info (name bound vs module-level). C2 is therefore DOWNGRADED:
> graph-grounded impact = importers-with-binding + exact same-file call
> sites, compared against grep (which keeps file-level recall but adds
> comment/substring noise). The `test_graph_only_empty_pinned` test in
> `tests/test_impact.py` reopens this the day the extractor emits
> cross-file calls. The SELECTED ranking is unchanged (C2 still builds);
> only the claimed mechanism narrowed to what was measured.

## 98F1 withdrawal (2026-09-05) — C2 REOPENED, the correction was wrong

The correction above is **withdrawn in full**. Its measurement was an
artifact of our own tooling, not a property of the extractor.

`graphquery.load_graph` merged files with `edges.extend(data.get("edges"))`
over `rglob("*.json")`. Two defects, both silent:

1. **Wrong key.** `graphify-out/graph.json` stores relationships under
   `"links"`. Only the per-file AST cache fragments carry `"edges"`. So
   100% of the edges every consumer ever saw came from single-file
   extractions — **same-file by construction**. "Zero cross-file calls" was
   a restatement of the bug.
2. **Wrong scope.** `rglob` swept `cache/ast/` and the dated backup
   snapshots, so the merged graph served 36 nodes from `rolepresets.py` and
   the other modules cycle 81 deleted as though they were live.

Measured after the fix, same repo, same day:

| | before (bug) | after (98F1) |
|---|---|---|
| nodes / edges | 4789 / 8444 | 2328 / 4339 |
| `calls` edges | 1270 | 1598 |
| same-file / **cross-file** | 1119 / **0** | 692 / **892** |
| deleted-module nodes served | 36 | 0 |

Cross-file edges are AST-`EXTRACTED`, e.g.
`src/codemonkey/exec.py:427 -> load_instructions() @ instructions.py`.
Live `compare()` on `journal.record` now reports **graph_only = 12** —
twelve caller files the graph finds and `search` misses — against
search_only = 18 (comment/substring noise). That is C2's original premise,
confirmed, on the measurement that was supposed to refute it.

**C2 is REOPENED at full scope:** graph-grounded impact = importers with
binding info **plus cross-file caller edges**, not importers alone.

**The lesson, recorded because it cost a cycle.** `test_graph_only_empty_pinned`
was written to reopen this question "the day the extractor learns cross-file
calls". It could only detect that the evidence CHANGED; it could not detect
that the evidence was WRONG when written, and it asserted a remembered
number rather than the graph file's own content. R-L makes citations
verifiable against the tree; this is its missing half — **a measurement that
contradicts a design premise is re-derived from primary data before the
premise is downgraded.** Three consumers (`graph_query` / `graph_path` /
`graph_explain`), the `codemonkey graph` CLI and `impact.py` had been
answering from per-file caches and stale snapshots since loop 28 without
anyone noticing, because they did return *something*.
