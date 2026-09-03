# Loop 6 Research — Context Engineering Chosen by Measurement (CYCLE R6)

Date: 2026-09-02 · Method: live web search (4 queries, multiple sources each).
Ranking criterion unchanged: leverage for a **local ~27B-class model** with the
prompt-based tool protocol in **headless autonomous runs**.

**Entry condition (charter):** loop 5 shipped an eval harness that can score two
configurations of the same agent on the same tasks — SATISFIED (cycles 24/25:
`codemonkey eval` + versioned baseline + regression gate). R6 proceeds.

## Researched capabilities

### 1. Compaction strategy bake-off (measured, not argued)
- Sources:
  - https://n4n.ai/blog/sliding-window-vs-summarization-managing-agent-memory/ —
    sliding window vs summarization tradeoffs for agent memory.
  - https://www.agentnative.dev/patterns/context-compaction-pattern-for-long-running-agents —
    canonical rebuild order: verbatim task head → summary block → recent turns →
    current tool schemas (our auto-compaction already matches this shape).
  - https://arxiv.org/abs/2605.23296 — parallel compaction; per-block summary
    volume control at matched quality.
- Why high-leverage: we ship two compaction strategies (summarizing,
  sliding-window) and cycle-15's invariants, but have NO measurement of which
  wins on real tasks. The eval harness can run identical golden tasks with
  `CODEMONKEY_STRATEGY_COMPACTION=<name>` and compare pass_rate/tokens/wall.
- Cost: 1 cycle (bake-off runner writing strategy-scoped baselines). **SELECTED.**

### 2. KV-cache measurement harness (prompt-cache payoff, measured)
- Sources:
  - https://github.com/ggml-org/llama.cpp/discussions/13606 — llama-server exposes
    `timings.cache_n` vs `prompt_n` in responses; the direct measurement signal
    for cache_hit ratio.
  - https://hexdocs.pm/llama_cpp_ex/007-prefix-caching.html — prefix-affinity slot
    selection explains when reuse happens vs not.
  - https://particula.tech/blog/prompt-reprocessing-swa-hybrid-models-kv-cache —
    reprocessing costs and model-dependent cache behavior.
- Why: cycle 22 added `cache_prompt` passthrough + prefix stability on faith.
  The server's timings tell us the REAL cached-prefix ratio per call. Extending
  the eval harness to record `cache_n/prompt_n` per task turns "prefix stable"
  into a measured number — and future refactors get a regression signal.
- Cost: 1 cycle (parse timings from provider responses into cost/eval telemetry).
  **SELECTED.**

### 3. Tool-result spill (disk pointer instead of truncation)
- Sources:
  - https://waylandz.com/ai-agent-book-en/chapter-36-tool-result-budget-and-spill —
    "truncate and the model re-reads; spill it to disk with a pointer and it
    doesn't have to."
  - https://pi-docs.aiuo.net/spec/03-runtime/16-tool-result-limits — per-tool-class
    budgets beat one shared cap.
- Why: cycle 17's observation budget truncates with a PARTIAL marker; the model
  then often re-runs the command (measured cost: double tokens, double wall).
  Spilling oversized outputs to `~/.codemonkey/spill/` and returning head+tail
  plus a file path lets `read_file`/`search` fetch the relevant slice on demand.
- Cost: 1–2 cycles. **SELECTED** (1 cycle: spill + head/tail + pointer in PARTIAL
  marker; per-class budgets deferred).

### 4. Context-window telemetry / context-rot tracking
- Sources:
  - https://www.trychroma.com/research/context-rot — performance degrades
    sub-linearly with input tokens even on needle tasks; near-perfect NIAH
    scores hide real degradation.
  - https://arxiv.org/html/2605.12366v1 — long-context weakness degrades monitor
    performance in agentic settings.
- Why: knowing tokens per turn (cycle 26) is not knowing whether quality rots as
  the window fills. A per-task "window depth" field (prompt size at each turn)
  in eval results lets the bake-off correlate pass_rate with context depth.
- Cost: 1 cycle. **SELECTED** (folds into cycle 28's bake-off: record depth per
  turn alongside strategy — no separate cycle needed).

### 5. Submodular context selection engine (PACMS-style)
- Sources:
  - https://arxiv.org/pdf/2606.20047v1 — submodular selection over conversation
    turns, memory, tool outputs as a pluggable engine.
- Why interesting: principled replacement for our relevance heuristic (cycle 27).
  But it needs a measurement base first (which this loop builds), and its win on
  an 8-task local suite is speculative. **NOT SELECTED this loop** — revisit at
  R7 with bake-off data in hand.

## SELECTED (loop 6 build list)

1. **CYCLE 28 — compaction bake-off**: `codemonkey eval --strategy-matrix
   summarizing,sliding-window` runs the golden suite once per strategy,
   records pass_rate/tokens/wall/window-depth per strategy into
   build/eval/matrix.json, prints a comparison table.
   verify: unit (matrix runs both configs via patched exec, depth recorded,
   matrix.json shape, comparison table, ties allowed); live: matrix over the
   3-task golden-core suite on home server.
2. **CYCLE 29 — KV-cache telemetry**: provider surfaces `timings.cache_n /
   prompt_n` when present; cost summary + eval results record cache_hit ratio;
   `--cost-summary` prints it.
   verify: unit (timings parse, ratio math, absent-timings tolerance, summary
   line, eval field); live: repeated identical task shows cache_n > 0.
3. **CYCLE 30 — tool-result spill**: outputs over the observation budget spill
   verbatim to ~/.codemonkey/spill/<hash>.txt; the tool result becomes
   head+tail + `PARTIAL [full output: <path>]`; `read_file`/`search` can fetch
   slices; spill files pruned after 24h.
   verify: unit (spill file written with verbatim content, marker contains
   path, under-budget untouched, prune, retrieval via read_file); live: big
   seq output spills and the model reads the slice.

## R7 charter note

With bake-off + cache telemetry in hand, R7 (reliability & recovery) proceeds;
its core-design flag (session-state semantics changes) still requires the
user's go-ahead before any such cycle.
