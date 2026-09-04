# Loop 19 Research — Context Budgeting Under Tight VRAM (CYCLE R19)

Date: 2026-09-03 · Method: live web search (2 queries) + the shipped budget
surface (observation budget, compaction strategies, spill, token telemetry).

## Researched capabilities

### 1. VRAM-aware context budget (tokens → bytes → config)
- Sources:
  - https://www.sitepoint.com/kv-cache-survival-guide-local-llms/ — per-token
    KV bytes = 2 (K+V) × layers × kv_heads × head_dim × bytes-per-weight; a
    working calculator.
  - https://contextwindowvramcalculator.com/ — formula-first calculator.
- Why: `context_limit` today is a raw token number the operator guesses. A
  `codemonkey budget` command that converts VRAM budget + model metadata
  (layers/Heads/dim, from the server's model info when exposed) into a
  safe context_limit + observation_budget, printed as copiable config.
  **SELECTED (cycle 56).**

### 2. Budget allocation across components (BaKlaVa-style priority)
- Source: https://arxiv.org/html/2502.13176v2 — budgeted per-layer KV
  allocation beats uniform truncation.
- Why (client-side analog): the run budget covers system + repo-map +
  memory + history + observation; allocate by priority (system > memory >
  recent history > repo-map density) with explicit per-component caps
  instead of a single observation cut. **SELECTED as design constraint on
  cycle 56 (budget report shows per-component share); a full allocator is
  server-side work — NOT SELECTED.**

### 3. KV offload to NVMe
- Source: https://runaihome.com/blog/nvme-kv-cache-offloading-local-llm-consumer-gpu-2026/ —
  spilling context to SSD buys capacity for 24GB GPUs.
- Why: server-side again (llama.cpp cache types). **NOT SELECTED.**

## SELECTED (loop 19 build list)

1. **CYCLE 56 — `codemonkey budget` calculator**: `budget --vram-gb 24
   --quant-gb 4 --max-model-len N` (or --model to fetch server metadata when
   available) → recommended context_limit + observation_budget split with
   per-token KV math (layers/kv_heads/head_dim with sane defaults for the
   Qwen3.8-27B class), prints a copiable YAML block + the per-component
   priority split note. Fails honestly when metadata is missing (asks for a
   --layers/--kv-heads/--head-dim override).
   verify: unit (≥6 tests: per-token bytes formula, safe-limit rounding under
   a VRAM cap, YAML block generation, metadata-missing honest error, override
   flags honored, observation budget = 40% of context default).
