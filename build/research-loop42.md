# Loop 42 research: the small-model compiler (CYCLE R42)

**Date:** 2026-09-05 · **Charter:** `build/loops-38-45-proposal.md` (R42) ·
**Entry condition FULFILLED:** R40 closed (without a machine success signal
this loop cannot be measured — the C93/C95 gates are that signal).
**Core-design PARTIAL:** per-segment tool restriction changes the advertised
tool surface mid-run — **R42 ENDS BY ASKING.**

**Question** (charter): open-weight models in this size class are reported
adequate at short-horizon structured tool use and shaky on long-horizon
coordination. This repo's entire premise is a local 27B endpoint. Can the
scaffold *compile* long-horizon tasks into short-horizon segments the
endpoint can actually execute — and how much of the frontier gap does that
close?

**Published numbers, UP FRONT (R-G) — and the ceiling warning:** the
capability ladder for tool use is the Berkeley Function-Calling
Leaderboard (https://gorilla.cs.berkeley.edu/leaderboard.html, v4 scores
via https://benchlm.ai/benchmarks/bfcl-v4): frontier models sit far above
any 27B-class open-weight entry, and BFCL is single-call accuracy, an easier
game than multi-turn coordination. The literature direction is consistent:
small LLMs are weak tool learners without help (EMNLP 2024,
https://arxiv.org/html/2401.07324v2); targeted fine-tuning can make small
models beat large ones at *narrow* tool calling
(https://arxiv.org/html/2512.15943); workflow scaffolding closes part of the
gap (fastWorkflow, https://dl.acm.org/doi/10.1145/3786335.3813158); and the
practitioner rule is extreme decomposition
(https://www.mohdvasim.com/blog/22-slm-task-decomposition). Stated plainly
before any work: the long-horizon tier may remain out of reach on this
endpoint. "Segmentation buys +N points and the tier is still out of reach"
is a valid exit, as R13 permitted.

## In-repo evidence (this repo, not literature)

- `argvalidate` (loop 20) catches malformed/hallucinated tool calls AFTER
  the fact — the failure mode it counts is exactly what per-segment surface
  restriction would prevent before the fact.
- `jobs` (loop 12) is already a durable state file: segment hand-off state
  is composition, not new machinery.
- The eval harness reports pass rate but never malformed-call rate; the
  loop cannot currently see the failure mode it wants to fix.
- No constrained/grammar decoding exists; the prompt tool protocol is the
  only contract, tightened nowhere per segment.

## Candidates (each: name, why, citations)

### C1 — Segment into short, individually verifiable units
Long-horizon task → segments with explicit hand-off state in `jobs`, each
with its own verify check (C93 gate per segment). Why: converts one
unverifiable horizon into N verifiable ones; matches the "extreme
decomposition" practitioner rule.

### C2 — Per-segment tool-surface restriction
Each segment advertises only the tools it needs (e.g. a research segment
gets `search` but not `write_file`). Why: the prompt protocol's failure
mode is malformed/hallucinated calls; fewer advertised tools, fewer ways
to be wrong. Core-design PARTIAL — the advertised surface changes mid-run.

### C3 — Malformed-call rate as a first-class metric
Count schema-mismatch/malformed calls per task in eval, ON vs OFF. Why: the
loop's effect must be visible separate from pass rate (a segment can fail
cleanly or fail malformed — different problems).

### C4 — Prompt-protocol tightening per segment
Constrained output shapes where the endpoint supports it, stricter
grammars where it does not. Why: cheap, no new machinery; sets the floor
before segmentation claims credit.

### C5 — Capability-ladder measurement (BFCL-adjacent)
A small local ladder (single-call → multi-call → multi-turn with state)
run against this endpoint, reported next to BFCL per R-G. Why: tells us
which tier we are compiling *for* instead of guessing.

### C6 — Fine-tune the endpoint (REJECTED — see below)
Targeted fine-tuning is the literature's strongest small-model lever
(2512.15943), but it is outside this repo's premise (a scaffold around a
fixed local endpoint, no training pipeline, no eval budget for it).
Rejected; recorded so a later reader knows it was considered.

## SELECTED (ranked)

1. **C5 first** — measure the ladder before compiling for it.
2. **C4 then C1** — tighten the protocol, then segment with per-segment
   verify; ON-vs-OFF probes report pass rate AND malformed-call rate.
3. **C2** — per-segment restriction, only as far as the ask approves.
4. **C3** — throughout: the metric that makes C1/C2 claims checkable.
5. **C6** — rejected (out of premise).

## Cost note (R-F, charged against the loop that spends it)

Segmentation multiplies verify runs (one gate per segment); ladder
measurement is pure endpoint time on short prompts. Both reported per
probe; certified under R-H.

## ASK (R42 ends by asking — core-design PARTIAL)

1. Authorize per-segment tool-surface restriction (the advertised tools
   change mid-run, C2)?
2. Accept the ceiling term: if segmentation buys points but the
   long-horizon tier stays out of reach on the 27B endpoint, the loop exits
   with that stated plainly rather than escalating to fine-tuning (C6)?
