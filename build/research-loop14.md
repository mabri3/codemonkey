# Loop 14 Research — Heterogeneous Models & Routing (CYCLE R14)

Date: 2026-09-03 · Method: live web search (2 focused queries) + carried
evidence (the repo lost ~2 days of live acceptance to one wedged endpoint;
config already carries multiple providers + protocols).

## Researched capabilities

### 1. Availability failover (secondary provider on transport/auth failure)
- Sources:
  - https://nhimg.org/faq/what-is-the-difference-between-llm-fallback-and-llm-failover —
    fallback is request-level retry/switch; failover is endpoint-level.
  - https://portkey.ai/blog/failover-routing-strategies-for-llms-in-production —
    ordered targets with per-target overrides; on-failure move to next.
  - https://arxiv.org/html/2607.15899v1 — stateful failover is hard (session
    state must move with the route).
- Why: the repo's OWN history is the strongest evidence — three server outages
  blocked live acceptance. A `fallback_provider` config (provider name + same
  protocol) tried on transport/timeout errors (NOT on auth or tools-500) with
  the journal recording the route switch is directly motivated. Session state
  moves naturally: our sessions are conversation-logs, not server state.
- Cost: 1 cycle. **SELECTED.**

### 2. Complexity-based routing (small model for easy turns)
- Sources:
  - https://aicost.tools/blog/llm-model-routing-by-complexity/ — classifier-
    based routing evidence; small front-door routers are viable.
  - https://neuraltrust.ai/blog/llm-model-routing — cascade strategies.
- Why interesting: on ONE home server there's one model; a second model
  (e.g. a 1-4B classifier) doubles local memory pressure. Defer until a
  second local endpoint exists. **NOT SELECTED** (no second model locally;
  the fallback cycle covers the reliability half).

### 3. Semantic routing (embeddings-based)
- Sources: https://neuraltrust.ai/blog/llm-model-routing — semantic routing.
- Why: needs an embedding model + index — heavy machinery for a CLI.
  **NOT SELECTED.**

### 4. Cascade evaluation (try cheap → escalate on quality miss)
- Sources: https://neuraltrust.ai/blog/llm-model-routing.
- Why: needs a quality judge per turn — that's the eval harness's job
  offline, not in-run. **NOT SELECTED** (revisit with the R11 ROI data).

## SELECTED (loop 14 build list)

1. **CYCLE 47 — availability failover**: config `fallback_provider: <name>`;
   on transport/timeout errors after retries exhaust, exec re-runs the turn
   against the fallback provider (same protocol family), journal records the
   route switch with the error class; delegate children inherit it.
   verify: unit (≥6 tests: fallback on transport/timeout, no fallback on
   auth/tools-500, journal route-switch record, retry-exhaustion precondition,
   config default off, provider must exist).
2. **CYCLE loop14-final — acceptance**: sweep + report.
