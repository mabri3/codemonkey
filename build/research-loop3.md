# Loop 3 Research — Next 10x Improvements (CYCLE R3)

Date: 2026-09-02 · Method: live web search (6 queries, multiple sources each).
Ranking unchanged: leverage for a **local 27B-class model** with prompt-based tool
protocol, in **headless autonomous runs** (our dominant usage).

## Researched capabilities

### 1. Self-heal loops on failed edits/tests (Aider-style reflection)
- Sources:
  - https://github.com/NousResearch/hermes-agent/issues/536 — Aider's self-correction:
    failed edit / lint error / test failure → automatically re-prompt with the error.
  - https://getautonoma.com/blog/self-healing-test-automation — failure→fix agents.
- Why high-leverage HERE: our SREP blocks now produce precise, structured failure
  messages (near-miss anchors) — the missing half is feeding those errors back for an
  automatic retry turn instead of failing the run. Small models benefit most: they
  make more mistakes, so a cheap retry loop compounds.
- Cost: 1–2 cycles (edit-failure → auto re-prompt with error text, N retries).

### 2. Tool-output truncation with continuation (observation budget)
- Sources:
  - https://solana.garden/guides/llm-agent-tool-result-summarization-truncation-explained/ —
    observation budgets; 180KB tool output poisoning a context.
  - https://github.com/openai/openai-agents-python/blob/fea17ef5/src/agents/extensions/tool_output_trimmer.py —
    trimming large tool outputs from older turns at call time.
  - https://agentpatterns.ai/tool-engineering/graceful-tool-output-truncation/ —
    PARTIAL signal pattern: prefix + distinct truncation marker + continuation handle.
- Why high-leverage: our shell/search tools already hard-truncate at 20k chars, but
  nothing reserves budget across MULTIPLE large outputs in one turn — a single run
  with 3 fat greps can still blow the 32k window pre-compaction. Budget-aware
  truncation + PARTIAL handles (offset continuation) prevents eviction of the
  actual task.
- Cost: 1–2 cycles.

### 3. Repo map / symbol index (tree-sitter lite)
- Sources:
  - https://github.com/JaredStewart/coderlm — tree-sitter symbol table + xrefs API.
  - https://arxiv.org/html/2604.18413v2 — tree-sitter entity extraction for retrieval.
  - https://aider.chat style repo map (referenced widely in the above).
- Why: a compact symbol map (defs + line ranges per file) injected into system
  context lets a 27B model find targets without full-file reads. BUT: needs
  tree-sitter grammar deps for real fidelity; a regex-graded def-scan (def/class/
  function patterns per language) gets ~80% of the value at zero deps.
- Cost: 2 cycles. **Deferred — heavy for loop 3**; revisit post-acceptance.

### 4. Dry-run / plan-preview mode (`--plan` gate)
- Sources:
  - https://lillytechsystems.com/ai-school/ai-agent-safe-coding/dry-run-patterns.html
  - https://sallyport.dev/blog/dry-run-endpoints-ai-agents — preview planned changes
    + validation before writes.
- Why medium: our approval layer + checkpoints already de-risk mutations; plan mode
  adds certainty but duplicates the soft-deny surface for scripted runs.
- Cost: 1 cycle. **Deferred — overlaps approvals+checkpoints.**

### 5. Streaming partial-JSON for structured output UX
- Sources:
  - https://www.reddit.com/r/LLMDevs/comments/1l3g9ok/streaming_structured_output_whats_the_best/
  - https://www.digitalapplied.com/blog/llm-structured-output-json-reliability-production
- Why low for us: our exec mode is headless (final JSON to file); streaming partial
  JSON is an interactive-UX nicety.
- Cost: 1–2 cycles. **Not selected.**

## SELECTED (loop 3 build list)

1. **Self-heal edit retries** → `CYCLE 16` (`loop3:`): on edit_file/SREP failure
   (near-miss anchors present), the loop auto-issues ONE corrective re-prompt turn
   with the failure text; configurable `max_edit_retries` (default 1). Verify: unit
   (failure→retry→success with mock provider), suite green, live EDL probe.
2. **Observation budget for tool outputs** → `CYCLE 17` (`loop3:`): per-run tool-output
   budget (default 24k chars); over-budget outputs truncated to prefix + `[PARTIAL:
   N chars elided — rerun tool with narrower args]` marker; budget accounting in the
   loop. Verify: unit tests (budget enforcement, marker format, per-call isolation),
   suite green.
3. Then `CYCLE loop3-final`: full A1–A20 re-sweep + loop3 probes, final BUILD_REPORT
   section (all three loops), **request user acceptance (Gate 2)**.
