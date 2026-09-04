# Changelog

## 1.1.0 (2026-09-03)

Loops 17-26: honest-completion gate (`--verify-claims`), static model routing
(`model_routing` + `eval --route-stats`), unload-fallback rerouting for
single-slot servers, model-affinity task batching, `codemonkey budget`
VRAM→tokens calculator, tool-arg validation gate, `codemonkey digest`,
`exec --dry-run`, env quarantine for tests + sweep offline guard, delegate
`role_presets`, watch frames + `digest --last`, verify-gate suggestion.

## 1.0.0 (2026-09-03)

Final v1.0 closing the 16-loop arc: delegation ROI (roles + adversarial review
rounds), durable jobs across runs, lessons with verified-by-eval adoption,
availability failover, operator status surface, hardening (secret redaction,
supply chain, THREAT_MODEL).

## 1.0.0-rc1 (2026-09-03)

Release candidate closing the loop 1-10 arc. Gate 2 (user acceptance) pending.

### Core agent
- Multi-provider (OpenAI + Anthropic wire protocols, raw httpx, no SDKs)
- Prompt-based tool protocol with auto-fallback from native tools (llama.cpp
  HTTP-500 verified); native→prompt bridge for text-wrapped tool calls
- 13 tools incl. batched multi-file atomic SREP edits, repo map (relevance-
  ranked, budget-capped injection), delegate/delegate_batch sub-agents
- Rule-based permissions (deny→ask→allow) layered before approval policies
- Approval policies, sandbox levels, checkpoint/undo (workspace-scoped)

### Reliability
- Execution journal with failure-class taxonomy; idempotent mutating tools
- Verify gate with bounded corrective turns
- Provider retry/backoff (Retry-After, full jitter; tools-500 immediate)
- Streaming wall-clock guard (anti-wedge)

### Context engineering (measured)
- Auto-compaction (summarizing/sliding-window, bake-off measurable)
- Prompt-prefix stability + cache_prompt (99% measured cache hit)
- Observation budget + verbatim spill + deterministic output slimming
- Repo-map relevance ranking from the task prompt

### Observability
- JSONL event streams, --cost-summary + cumulative cost ledger, journal
  forensics CLI, eval harness with golden suites/baselines/regression gate

### Docs
- README rewrite; features.html per-cycle ledger; AGENTS.md operating
  contract (graphify mandate); per-loop BUILD_REPORTs

### Known limitations
- A9-class probes (heavy multi-tool loops) exceed local 27B hardware latency
  budgets; recorded BLOCKED-slow rather than faked
- shell cwd-escape is a documented standing limitation (loop-9 charter)
