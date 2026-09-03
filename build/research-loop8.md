# Loop 8 Research — Throughput & Cost Control (CYCLE R8)

Date: 2026-09-02 · Method: live web search (2 focused queries + carried data
from loops 5-6 measurements). Ranking criterion: local ~27B headless runs.

**Carried data (from loops 5-6, measured):** cache hit 99% on repeated prefix;
bake-off: summarizing 3.66s vs sliding-window 10.8s wall on identical tasks;
token totals now tracked per run (cost.json); spill eliminates re-run costs.

## Researched capabilities

### 1. Batched edits — `edit_file` accepting multiple SREP blocks (multi-file)
- Sources:
  - https://zylos.ai/research/2026-03-03-ai-agent-tool-use-optimization —
    sequential tool loops waste turns; batching cuts round-trips.
  - https://github.com/patchloom/patchloom — batch multiple file edits into a
    single tool call (all-or-nothing apply).
- Why: our SREP blocks already support multi-block single-file edits (cycle
  13); extending `edit_file` to accept a list of {path, blocks} applies N
  files in ONE tool call — fewer model turns = fewer giant-prompt round-trips,
  the dominant cost on a 27B local model.
- Cost: 1 cycle. **SELECTED.**

### 2. Tool-result whitespace/index compaction (output slimming)
- Sources:
  - https://machinelearningmastery.com/prompt-compression-for-llm-generation-optimization-and-cost-reduction —
    compression must preserve task-relevant meaning.
  - https://github.com/pleasedodisturb/awesome-llm-token-optimization —
    quick wins: strip, dedupe, truncate predictable noise.
- Why: shell outputs carry banner/whitespace noise (e.g. seq outputs,
  ls columns). A cheap deterministic slimming pass (collapse >2 blank lines,
  strip trailing spaces) before the observation budget shrinks tokens without
  LLM involvement — measured per run in the journal.
- Cost: 1 cycle. **SELECTED.**

### 3. Transport reuse verification (no code change expected)
- Sources:
  - https://www.python-httpx.org/advanced/clients/ — Client reuse = pooling +
    keep-alive; our providers already hold one Client per provider instance.
- Why: confirm one-client-per-run (no per-call connect) and document. The eval
  matrix spawns per-task providers — sharing one client across tasks is a
  possible micro-win but risks cross-task state; measured wall in loops 5-6
  showed connect overhead is negligible vs 27B inference seconds.
- Cost: 0 cycles (documented in report). **NOT SELECTED** (already present).

### 4. Prompt-cache payoff measurement (already done in cycle 29)
- Sources: loop-6 cycle 29 — 99% measured hit; matrix.json tracks depth.
- Status: DONE, carried. **NOT SELECTED** (already shipped).

### 5. Model routing (small model for easy turns)
- Sources:
  - https://github.com/pleasedodisturb/awesome-llm-token-optimization — model
    routing as a top quick-win.
- Why interesting: route trivial turns (single-word replies) to a smaller
  model. But on a single home server there is ONE model; routing adds config
  complexity for zero local gain today. **NOT SELECTED** (revisit for
  multi-server setups).

## SELECTED (loop 8 build list)

1. **CYCLE 34 — batched multi-file SREP edits**: `edit_file` args accept
   `edits: [{path, blocks}|{path, search, replace}]`; atomic all-or-nothing
   apply across files; result lists per-file outcomes.
   verify: unit (≥6 tests: multi-file apply, atomicity on mid-failure,
   single-file back-compat, per-file outcomes, journal entries per file,
   sandbox respected); suite green.
2. **CYCLE 35 — tool-output slimming**: deterministic pre-budget pass (collapse
   3+ blank lines to one, strip trailing whitespace, drop ANSI escapes);
   slimming stats (chars saved) recorded in journal outcome.
   verify: unit (≥5 tests: blank-line collapse, ANSI strip, trailing-space
   strip, stats recorded, under-threshold untouched); suite green.
3. **CYCLE loop8-final — acceptance**: sweep + report (transport reuse and
   cache payoff documented as carried/verified).
