# Loop 5 Research — Next 10x Improvements (CYCLE R5)

Date: 2026-09-02 · Method: live web search (6 queries, multiple sources each).
Ranking criterion unchanged: leverage for a **local ~27B-class model** with the
prompt-based tool protocol in **headless autonomous runs** — now that the home
llama.cpp server is live again, local-model constraints (32k context, KV-cache
reuse) are once again the primary optimization surface.

Entry note (R5 charter): subagents and hooks/permissions change **core design**
(loop architecture; sandbox + approval semantics). Per AGENTS.md, R5 ENDS by
asking the user before either is built.

## Researched capabilities

### 1. Local eval harness for the agent itself (golden tasks + trajectory scoring)
- Sources:
  - https://github.com/nishanttyagi28/agenteval — git-native, CLI-first, local-first
    YAML golden suites; reliability metrics vs a versioned baseline; regressions
    as reviewable CI decisions.
  - https://github.com/reaatech/agent-eval-harness — trajectory eval, tool-use
    correctness, cost-per-task, latency budgets, golden-trajectory regression suites.
  - https://github.com/RitikPatill/agent-eval-lab — capture execution traces, rubric
    scoring, local-first dashboards.
- Why highest-leverage: every future loop decision (compaction strategy choice,
  ranking weights, prompt-stability work) is currently argued from intuition. A
  golden-task harness that runs the real `codemonkey exec` against canned repos and
  scores exit code + tool trajectory + stdout contract converts loop-6's
  "context engineering chosen by measurement" from aspiration into machinery.
  Pure-Python, runs against the live local server, no new deps.
- Cost: 2 cycles (harness + ~8 golden tasks incl. the A-probes as tasks).
- **SELECTED.** Unlocks R6's entry condition.

### 2. Token/cost accounting per run (telemetry + budget enforcement)
- Sources:
  - https://inferensys.com/glossary/agentic-observability-and-telemetry/agent-cost-telemetry/token-accounting —
    systematic per-run token tracking as an ops requirement.
  - https://github.com/ai-agent-kit/agent-cost-tracker — real-time usage tracking
    with budget enforcement in agent loops.
  - https://prefactor.tech/learn/token-usage — agents amplify token cost; tracking
    per phase (tool loops vs final answers) is where the savings are.
- Why high-leverage: usage already flows in `turn.completed` events but nothing
  aggregates it. A run-summary (per-turn tokens, per-tool-call counts, wall time)
  written to the JSONL stream and a `cost.json` cumulative ledger gives the eval
  harness its second scoring axis and gives operators a spend dial
  (`max_turns` today is the only budget).
- Cost: 1 cycle. **SELECTED** (pairs with #1: the harness scores cost too).

### 3. Repo-map retrieval beyond symbols (content search integration)
- Sources:
  - https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents —
    curation beats accumulation; retrieval quality is the context lever.
  - https://arxiv.org/html/2604.18413v2 — entity/dependency extraction for retrieval
    (call-expression edges, not just defs).
- Why: cycle-21's map ranks by recency+density but has no *relevance* signal for
  the current task. Adding query-conditioned selection (reuse the existing `search`
  tool's index against the map) would let the injection pick task-relevant files.
- Cost: 1–2 cycles. **SELECTED** (one cycle: relevance ranking pass).

### 4. Subagents / delegated context isolation — CORE DESIGN
- Sources:
  - https://arxiv.org/html/2508.08322v1 — isolated subagent context windows;
    orchestrator receives only final results.
  - https://code.visualstudio.com/blogs/2026/02/05/multi-agent-development —
    context-isolated agents; intermediate work stays out of the main session.
  - https://hidekazu-konishi.com/entry/claude_code_subagents_and_orchestration_guide.html —
    scoped tasks, own system prompt + tool access.
- Why interesting: a 32k local context would benefit hugely from delegating
  wide-reads to throwaway contexts. But it changes the loop architecture
  (nested run_turns, event bubbling, budget inheritance), session-state
  semantics, and the approval surface. **CORE DESIGN — user decision required
  before building.**
- Cost: 3+ cycles.

### 5. Hooks + rule-based command permissions — CORE DESIGN
- Sources:
  - https://code.claude.com/docs/en/hooks-guide — deterministic allow/deny layer
    around tool execution; auto-approve specific patterns.
  - https://blakecrosley.com/blog/claude-code-hooks-explained — guarantees around
    a non-deterministic model via a deterministic gate.
- Why: our approvals layer is policy-shaped (untrusted/on-request/never) but has
  no per-pattern rules ("always allow git status, always deny rm -rf /"). A rules
  engine changes approval semantics and the sandbox contract. **CORE DESIGN —
  user decision required.**
- Cost: 2 cycles.

### 6. MCP client extension points — NOT SELECTED (fourth deferral, reasons stack)
- Sources:
  - https://docs.langchain.com/oss/python/deepagents/cli/mcp-tools — external tool
    servers via config, no agent modification.
  - https://blink.new/blog/cursor-mcp-json-guide — MCP as the bridge to external
    systems.
- Why still deferred: for a LOCAL 27B model, dynamic external toolsets dilute the
  prompt-protocol advertising and raise malformed-call rates; the fixed 11-tool
  surface is a deliberate small-model optimization. Revisit if a deployment needs
  org-specific tools.

## SELECTED (loop 5 build list)

Ranked by leverage ÷ cost:

1. **CYCLE 24** — eval harness core: `codemonkey eval` runs YAML golden tasks
   (prompt + expected stdout contains / exit code / required tool trajectory),
   scores pass rate + tokens + wall time, writes `build/eval/results.json`.
   [candidate 1]
2. **CYCLE 25** — golden task suite + regression baseline: ~8 tasks (pong, tool
   loop, structured output, resume, patch-edit, verify-gate fix), versioned
   baseline comparison, exit 1 on regression. [candidate 1]
3. **CYCLE 26** — token/cost telemetry: per-turn usage aggregation in the JSONL
   stream + `--cost-summary` + cumulative `~/.codemonkey/cost.json` ledger.
   [candidate 2]
4. **CYCLE 27** — repo-map relevance ranking: task-conditioned selection folded
   into the cycle-21 injection (still budget-capped, still opt-in). [candidate 3]

## ⚠️ CORE-DESIGN DECISIONS REQUIRED FROM THE USER (R5 ends here per AGENTS.md)

- **Subagents / delegated context isolation** (candidate 4): approve to design &
  build (3+ cycles, changes loop architecture + session semantics), or defer to
  a later loop.
- **Hooks + rule-based command permissions** (candidate 5): approve to design &
  build (2 cycles, changes approval/sandbox semantics), or defer.

After loop 5's non-core cycles (24–27) and the loop5-final re-sweep, R6 (context
engineering by measurement) opens with its entry condition satisfied by the
cycle-24/25 harness.
