# Loop 18 Research — Route-Aware Single-Slot Model Handling (CYCLE R18)

Date: 2026-09-03 · Method: live web search (2 queries) + the loop-17 incident
(A16: routing to a 2nd model unloaded the resident one on .176/LM Studio →
400 "No model loaded").

## Researched capabilities

### 1. Model-load reconciliation before routing (probe → load → proceed)
- Sources:
  - https://lmstudio.ai/docs/developer/core/ttl-and-auto-evict — idle TTL +
    auto-evict: models unload between requests by design; clients must
    tolerate/re-load.
  - https://www.reddit.com/r/LocalLLaMA/comments/1rhjc4x/ — production
    pipelines hit "No model loaded"-class errors from auto-unload.
  - https://lmstudio.ai/docs/cli/local-models/load — `lms load` with TTL
    exists CLI-side, but a CLI dependency is out; we use the wire.
- Why: codemonkey can't control the server's slot, but it can DETECT the
  400 "No model loaded"/"not loaded" response class and RE-ROUTE instead of
  failing the run: retry once against the default model (which the slot
  likely holds or auto-loads), journal a `model_unload_fallback` record.
  **SELECTED (cycle 54).**

### 2. llama.cpp router mode / llama-swap
- Sources:
  - https://runaihome.com/blog/llama-server-router-mode-multi-model-setup-2026 —
    server-side multi-model routing exists (llama-server router mode since
    2025-12); VRAM traps documented.
  - https://hivebook.wiki/wiki/llama-swap-on-demand-model-swapper-for-llama-cpp —
    llama-swap proxy swaps on demand.
- Why: SERVER-side solutions; codemonkey is the client and must work against
  a bare single-slot server (today's .176). Server choice stays the
  operator's. **NOT SELECTED as code; documented in the threat-model note.**

### 3. Model-affinity batching (group tasks by model to minimize swaps)
- Sources: carried — swap latency is seconds even with page cache
  (reddit llama-swap thread).
- Why: in `eval` / `delegate_batch`, sort pending tasks by routed model so a
  slot is loaded once per model per batch instead of ping-ponging.
  **SELECTED (cycle 55).**

### 4. Persistent multi-model slots
- Sources: lmstudio issue #706 (autoload last model) — server feature, not
  client. **NOT SELECTED.**

## SELECTED (loop 18 build list)

1. **CYCLE 54 — unload-fallback rerouting**: when a routed chat fails with
   the 400 "No model loaded"/"model not loaded" class, exec retries ONCE with
   the default provider/model, journals `model_unload_fallback` (with the
   failed route), and tags the task result. Delegate children inherit the
   behavior.
   verify: unit (≥5 tests: 400-unload detected → fallback applied + journaled,
   other 400s NOT swallowed, fallback failure propagates, tag on result,
   disabled without routing rules).
2. **CYCLE 55 — model-affinity batching**: `delegate_batch` / eval task
   ordering honors routed model (same-model tasks adjacent) via
   `batch_by_model(tasks, resolver)`; used by eval's task loop ordering.
   verify: unit (≥4 tests: grouping preserves order within group, groups
   ordered by first appearance, empty/single-task no-op, mixed routes).
3. **CYCLE loop18-final — acceptance**: sweep + report + push.
