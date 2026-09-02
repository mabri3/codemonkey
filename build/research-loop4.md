# Loop 4 Research — Next 10x Improvements (CYCLE R4)

Date: 2026-09-02 · Method: live web search (8 queries, multiple independent
sources each) + a fresh read of the built code (`src/codemonkey/`, 4,962 LOC,
197 tests green at `197 passed`). Ranking criterion is unchanged from loops
2–3: **leverage ÷ cost for a local 27B-class model driving headless,
scripted runs** — the dominant usage this CLI exists for.

Status note: loop3-final requested **Gate 2** (user acceptance). This research
cycle *proposes* loop 4; none of the `loop4:` cycles below are authorized to
build until the user answers Gate 2.

## Entry review — what is already built (grounding)

Verified by reading the source, not from the log:

- exec/REPL/review/sessions/config/models/undo commands; JSONL event contract;
  structured output + schema retry; resume; git guard; exit codes 0/1/2.
- Providers: OpenAI + Anthropic wire, hand-rolled SSE, native tool calls,
  `tool_protocol: auto` with the llama.cpp `tools`-500 → prompt fallback.
- Tools: read/write/edit(SREP)/list/glob/search/shell/update_plan/web_fetch,
  coarse sandbox gate in `tools.dispatch`, approval soft-deny.
- Loop: parallel tool execution, auto-compaction with system re-injection,
  self-heal edit retries, per-run observation budget, checkpoints/undo.

Two **defects** found during this read (they become fix cycles, per the
critic-loop convention — they map to `build/spec.md`, not to new research):

- **F-A — the memory strategy is built but never wired.**
  `strategies/memory.py` implements `FileMemory`/`NoMemory` and
  `strategies.build()` instantiates one, but nothing calls `load()`:
  `grep -rn "memory" src/codemonkey/exec.py src/codemonkey/loop.py` returns
  no injection site, and `tools/__init__.py::_MODULES` has no `update_memory`
  entry. spec.md ("Memory … injected into the system prompt … via an
  `update_memory` tool") is therefore unmet — the selector passes A19/A20
  because those probes only cover compaction + session-state.
- **F-B — the loop-3 knobs are not knobs.** `run_turns(max_edit_retries=1,
  observation_budget=24000)` are function defaults only; neither name appears
  in `config.py` DEFAULTS/ENV_MAP nor in `exec.py`'s call, so the documented
  "configurable `max_edit_retries`" / "per-run budget" cannot be set by a
  user. (BUILD_LOG scoped them to `run_turns` honestly; plan.md advertised
  them as knobs.)

## Researched capabilities

### 1. Verification inside the loop (post-mutation verify gate)
- Sources:
  - https://momentic.ai/blog/verification-belongs-inside-the-agent-loop —
    gate vs loop: the failure output goes *back into the agent's next move*,
    looping until green or a retry limit.
  - https://dev.to/shipwithaiio/how-to-build-a-self-verification-loop-in-claude-code-3-layers-20-minutes-m1p —
    3 layers (syntax/intent/regression); the test-runner layer is called the
    highest-ROI single addition.
  - https://paelladoc.com/blog/verification-loops/ — "self-reported success is
    a claim shaped exactly like proof, with none of the substance".
  - https://www.futureproofing.dev/resources/ai-native-team/agentic-coding-workflow-2026 —
    plan-build-test-ship as the 2026 default loop.
- Why highest-leverage HERE: our self-heal cycle (16) only reacts to *edit*
  failures — a syntactically applied edit that breaks the build ends the run
  with a confident wrong "done". Headless runs are exactly where nobody is
  watching. We already have every part needed (shell tool, observation budget,
  corrective re-prompt machinery from cycle 16); what is missing is the
  trigger + feedback wiring.
- Cost: 1 cycle.

### 2. Repo map / symbol index (third appearance — deferred in loop 3)
- Sources:
  - https://aider.chat/docs/ctags.html — repo map as ranked defs+refs context.
  - https://agentpatterns.ai/context-engineering/repository-map-pattern/ —
    AST + PageRank ranking of the map under a token budget.
  - https://arxiv.org/html/2603.27277v1 — tree-sitter symbol graphs for LLM
    code exploration.
  - https://anthonywest.co.uk/research/code-intelligence-indexing-2026-openai —
    2026 shift: precompute structure, expose it as a tool, stop burning
    context on broad file reads.
  - https://agenticskillset.org/en/topics/repo-maps-file-summaries/ — repo
    maps + file summaries as the standard token-optimization layer.
- Why now: loop 3 deferred it as "heavy" only because fidelity seemed to need
  tree-sitter grammars. A dependency-free regex def-scan (def/class/func/type
  patterns per language) + mtime-keyed cache gets most of the value; a 27B
  model's dominant failure is *finding* the edit site, and every wasted
  `read_file` is 2–8k tokens of a 32k window.
- Cost: 2 cycles (index+cache+tool · injection+ranking+budget).

### 3. Prompt-prefix stability / KV-cache reuse (local-server specific)
- Sources:
  - https://github.com/ggml-org/llama.cpp/discussions/13606 — KV cache reuse
    with llama-server; `cache_prompt`, slot similarity threshold, `id_slot`.
  - https://www.mykolaaleksandrov.dev/posts/2026/06/claude-code-llamacpp-prompt-cache-fix/ —
    a coding agent's own volatile prompt prefix silently killing the cache.
  - https://7minai.com/how-to-fix-llama-server-kv-cache-reuse/ —
    `--cache-reuse N` as the highest-impact server flag.
  - https://particula.tech/blog/prompt-reprocessing-swa-hybrid-models-kv-cache —
    full prompt re-processing costs on large agent prompts.
  - https://arxiv.org/pdf/2311.04934 — Prompt Cache: modular attention reuse.
- Why high-leverage HERE: our target *is* a llama.cpp server, and every turn
  resends the whole stack. Cache reuse depends on a byte-stable prefix; we
  currently rebuild the system block per turn (dict-ordered tool specs) and
  compaction rewrites the head, which invalidates the whole slot. This is a
  pure-latency 10x on the one deployment the spec names, and it is testable
  offline (prefix-identity invariant) even while the home server is wedged.
- Cost: 1 cycle.

### 4. Project-instruction loading (AGENTS.md / CLAUDE.md)
- Sources:
  - https://blog.buildbetter.ai/agents-md-complete-guide-for-engineering-teams-in-2026/ —
    build/test commands + conventions as the agent's project contract.
  - https://devtk.ai/en/blog/what-is-agents-md-guide/ — read natively by
    Claude Code, Codex CLI, Cursor, Aider, Gemini CLI, Copilot, Q.
  - https://codersera.com/blog/agents-md-complete-guide-2026/ — spec donated
    to the Linux Foundation's Agentic AI Foundation (Dec 2025).
  - https://arxiv.org/pdf/2606.07448 — measured adoption of agent instruction
    files in new GitHub projects.
- Why high-leverage: a small model follows explicit local conventions far
  better than it infers them, and this repo already *has* an AGENTS.md that
  `codemonkey` itself cannot read. Pairs naturally with fix F-A (memory
  injection) — one stable "project context" section in the system prompt.
- Cost: 1 cycle (+ folds F-A in).

### 5. Provider resilience: retry/backoff with Retry-After + jitter
- Sources:
  - https://machinelearningplus.com/gen-ai/resilient-llm-client/ — retry +
    fallback ladder for LLM clients.
  - https://www.learnwithparam.com/blog/retry-patterns-llm-api-errors-production —
    retry only 429/500/502/503/504/529; ~4 attempts is the sweet spot.
  - https://apxml.com/courses/building-advanced-llm-agent-tools/chapter-4-integrating-external-apis-tools/api-rate-limits-retries-tools —
    honoring `Retry-After` instead of guessing.
  - https://flatkey.ai/blog/llm-rate-limits-explained-rpm-tpm-retries — RPM/TPM
    limits and client-side retry behavior.
- Why: `grep -rn "retry\|backoff\|429" src/codemonkey/providers/` returns
  nothing — one transient 503 or a hosted provider's 429 kills a long headless
  run outright. Cheap and bounded. **Constraint:** the retry path must NOT
  swallow the tools-parameter 500, which is acceptance ground truth (A9) —
  that error must still raise immediately so `auto` falls back to prompt mode.
- Cost: 1 cycle.

### 6. Subagents / delegated context isolation — DEFER to loop 5
- Sources:
  - https://arxiv.org/pdf/2510.26493 — Context Engineering 2.0: delegation as
    active context management; orchestrator receives results, not traces.
  - https://hidekazu-konishi.com/entry/claude_code_subagents_and_orchestration_guide.html —
    isolated context windows, parallel fan-out, custom agent definitions.
  - https://arxiv.org/pdf/2606.09730 — SearchSwarm: delegation for long-horizon
    work.
- Verdict: genuinely high leverage for long runs, but it changes the core loop
  architecture — AGENTS.md requires stop-and-ask before that. Also doubles
  token cost per delegated subtask, which is the wrong trade on a single local
  27B server. **Loop 5 candidate, user-gated.**

### 7. Hooks + fine-grained permission rules — DEFER to loop 5
- Sources:
  - https://code.claude.com/docs/en/agent-sdk/hooks — PreToolUse/PostToolUse
    lifecycle interception; deny > ask > allow precedence.
  - https://hidekazu-konishi.com/entry/claude_code_hooks_complete_guide.html —
    deterministic enforcement across the tool lifecycle.
  - https://www.morphllm.com/claude-code-hooks — command allow/deny-listing and
    secret-file protection as the canonical PreToolUse use case.
- Verdict: our approval layer is tool-granular (`shell` all-or-nothing); rule-
  based command matching would be strictly better. But it modifies **sandbox
  and approval semantics** — core design, stop-and-ask territory. **Loop 5,
  user-gated.**

### 8. Local eval harness for the agent itself — DEFER to loop 5
- Sources:
  - https://arxiv.org/pdf/2605.27922 — Harness-Bench: 106 local sandboxed
    end-to-end tasks; local execution kills benchmark drift.
  - https://github.com/rasbt/local-coding-agent-evals — small coding tasks in
    isolated workspaces aimed at local models.
  - https://arxiv.org/pdf/2605.23950 — harness effects dominate model
    comparisons; disclose and measure the harness.
  - https://www.kdnuggets.com/top-10-open-source-benchmarks-for-ai-coding-agents-in-2026
- Verdict: strong — after four loops of improvements we still cannot *measure*
  whether loop N made the agent better; every claim rests on unit tests plus
  one-off live probes. Held for loop 5 only because loop 4 is already 7 cycles
  and an eval harness is worth its own dedicated loop.

### 9. MCP client / config-declared tools — NOT SELECTED (third deferral)
- Sources:
  - https://contextbolt.com/blog/ai-tools-mcp-support/ — MCP support across
    2026 tools.
  - https://www.pulsemcp.com/clients — 600+ clients; ecosystem is now plumbing.
  - https://www.verdent.ai/guides/codex-cli-mcp-setup-guide — Codex CLI's MCP
    wiring as the closest analogue to ours.
- Verdict unchanged from loop 2: real ecosystem value, but it is surface area
  rather than core-loop leverage, a fixed well-documented toolset suits a 27B
  model better, and it carries sustained maintenance cost. Revisit only if the
  user has a concrete external-tool need.

## SELECTED (loop 4 build list)

Ranked by leverage ÷ cost for local-model headless operation. Fix cycles first
(they are prerequisites: F-A defines the project-context block that cycle 18
extends and cycle 22 must keep byte-stable; F-B supplies the config plumbing
cycle 19 reuses).

0. **CYCLE 7F1** — wire the memory strategy (spec gap F-A): `load()` injected
   into the system prompt, `update_memory` registered as a tool, both disabled
   by `memory: none`.
1. **CYCLE 17F1** — expose `max_edit_retries` + `observation_budget` as real
   config/env knobs (gap F-B).
2. **CYCLE 18** (`loop4:`) — project-instruction loader (AGENTS.md → CLAUDE.md
   → `.codemonkey/instructions.md`), size-capped, gate-able, merged with
   memory into ONE stable project-context block. [candidate 4]
3. **CYCLE 19** (`loop4:`) — verify gate: run the configured `verify_command`
   after mutating turns, feed failures back for bounded corrective turns.
   [candidate 1]
4. **CYCLE 20** (`loop4:`) — repo-map index + cache + `repo_map` tool.
   [candidate 2a]
5. **CYCLE 21** (`loop4:`) — repo-map ranking, budget, system-prompt injection.
   [candidate 2b]
6. **CYCLE 22** (`loop4:`) — prompt-prefix stability + `cache_prompt`
   passthrough for KV-cache reuse. [candidate 3]
7. **CYCLE 23** (`loop4:`) — provider retry/backoff honoring `Retry-After`,
   with the tools-500 fallback path explicitly preserved. [candidate 5]
8. **CYCLE loop4-final** — full A1–A20 re-sweep + loop-4 probes + BUILD_REPORT
   loop-4 section.

## Loop 5 preview (research-gated, NOT pre-selected)

`CYCLE R5` must re-research and re-rank with fresh citations before anything is
selected. Carried-forward shortlist: subagents/delegated context (6), hooks +
rule-based permissions (7), local eval harness (8), MCP client (9), plus
token/cost accounting. Items 6 and 7 change core design (loop architecture;
sandbox/approval semantics) — AGENTS.md requires stop-and-ask, so R5 ends by
asking the user, not by building.
