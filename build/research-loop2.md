# Loop 2 Research — 10x Improvement Candidates (Cycle 11)

Date: 2026-09-02 · Method: live web search (7 queries, multiple sources each);
no fabricated sources. Ranking criterion: leverage for a **local 27B-class model**
(prompt-based tool protocol, finite context) driving a **scriptable headless CLI**.

## Researched capabilities

### 1. Parallel tool execution
- Sources:
  - https://github.com/agentpatternscatalog/patterns/blob/main/patterns/parallel-tool-calls.md —
    model emits several independent calls per turn; host executes concurrently.
  - https://zylos.ai/research/2026-04-23-parallel-tool-calling-optimization-ai-agents/ —
    sequential loops compound latency; parallelization is a top wall-clock win.
  - https://airbyte.com/agentic-data/parallel-tool-calls-llm — up to 3.7x latency cuts.
- Why high-leverage here: our loop already parses MULTIPLE TOOL_CALL blocks per turn
  but executes them serially; multi-search/multi-edit prompts are common in our own
  probes. Local model + small budgets make per-turn round-trips expensive, so folding
  independent calls into one turn is a direct capability 10x in symptom, not concept.
- Cost: ~1 cycle (thread-pool execution of independent calls, ordered results).

### 2. Search/replace patch-based editing (fuzzy-tolerant edit tool upgrade)
- Sources:
  - https://www.agentpatterns.ai/tool-engineering/llm-edit-format-selection/ — diff vs
    search-replace vs whole-file: accuracy trade-offs for small models.
  - https://github.com/yasik/patch-tool — robust search/replace for LLM edits.
  - https://pypi.org/project/llm-patch-tool/ — atomic write, mode preservation, torn-write safety.
- Why high-leverage: whole-file rewrites are where a 27B model corrupts files (drops
  sections, re-indents). Search/replace blocks with exact-match + whitespace-tolerant
  fallback would materially raise edit success rates on the local model.
- Cost: 1–2 cycles (tool semantics + tests; keep `write_file` as fallback).

### 3. Checkpoints / rollback (snapshot-before-write with undo)
- Sources:
  - https://docs.codebolt.ai/docs/using-codebolt/chat/checkpoints-and-rollback —
    snapshot at every meaningful step; undo without touching git.
  - https://likeone.ai/blog/claude-code-checkpoints-rewind-guide-2026 — snapshot before
    each mutating tool call; rewind restores the tree.
  - https://codex.danielvaughan.com/2026/04/25/codex-cli-error-recovery-rollback-patterns-git-safety-nets —
    Codex CLI found built-in undo hard; git safety-net patterns instead.
- Why high-leverage: autonomous headless runs (our primary mode) can't ask the user
  before overwriting; a pre-write shadow copy + `/undo`/`--resume-rollback` semantics
  turn "failed autonomous run" from data-loss into a re-run.
- Cost: ~1–2 cycles (snapshot store in ~/.codemonkey/checkpoints, restore cmd).

### 4. Token-budget management / compaction trigger hardening
- Sources:
  - https://newsletter.victordibia.com/p/context-engineering-101-how-agents — compaction
    strategy study across Claude Code/Copilot CLI.
  - https://workos.com/blog/coding-agent-context-window-compaction-settings — reserve
    margins, threshold compaction mechanics.
  - https://arxiv.org/html/2606.22528v2 — governance decay: compaction can silently drop
    safety constraints; mitigations (re-inject system prompt post-compaction).
- Why high-leverage: our summarizing strategy exists but never runs automatically in
  the loop; wiring budget estimation + auto-compaction + post-compaction system-prompt
  re-injection makes long autonomous runs survive at 32k context (our real budget).
- Cost: 1–2 cycles (estimate → trigger maybe_compact in-loop + invariant test).

### 5. MCP-style extension points (custom tools from config)
- Sources:
  - https://modelcontextprotocol.io/community/seps/2133-extensions.md — composable
    optional extensions via identifier.
  - https://py.sdk.modelcontextprotocol.io/v2/advanced/extensions/ — opt-in tool bundles.
  - https://github.com/google-gemini/gemini-cli/blob/2139b121/docs/extensions/writing-extensions.md —
    Gemini CLI extensions: custom tools/commands via config.
- Why high-leverage: extensibility multiply the agent for org-specific workflows
  (our own build loop needs repo-specific tools); config-declared tools = no code
  changes for users. BUT: it is surface area, not core-loop leverage for a 27B local
  model — small models handle a fixed, well-documented toolset better than open-ended
  dynamic tools.
- Cost: 2–3 cycles; sustained maintenance burden. **Not selected for loop 2.**

### 6. Agentic sub-review (self-critique pass before final answer)
- Sources:
  - https://arxiv.org/html/2501.17167v1 — QualityFlow: quality-checker agent gates code.
  - https://arxiv.org/pdf/2607.13196 — agentic code review quality study.
- Why high-leverage-ish: our `review` command + critic-aligned system prompt already
  covers part of this; a built-in self-review turn on `exec` would improve output
  quality but at 2x token cost per run on a small model — poor ROI headless.
- Cost: 1 cycle. **Not selected for loop 2** (deferred; approvals/REPL already give
  interactive control).

## SELECTED (loop 2 build list — mapped to cycles)

Ranked by leverage ÷ cost for local-model headless operation:

1. **Parallel tool execution** → `CYCLE 12` (`loop2:`): execute independent tool calls
   from one turn concurrently (ThreadPool, results re-ordered to call order, event
   stream per call). Verify: unit test with 3 calls (2 slow sleeps) completes < serial
   time; live A9-style probe still green; suite green.
2. **Search/replace patch editing** → `CYCLE 13` (`loop2:`): `edit_file` upgrades to
   accept SREPs blocks (exact match → whitespace-tolerant fallback → explicit error),
   atomic write, plus failure diagnostics listing near-miss anchors. Verify: unit tests
   incl. fuzzy match + atomicity; live exec multi-file edit probe.
3. **Checkpoints / rollback** → `CYCLE 14` (`loop2:`): snapshot touched files before
   mutating tools; `codemonkey undo` restores the last checkpoint; `--list` history.
   Verify: unit tests (snapshot→mutate→restore byte-identical); live exec destructive
   edit then undo probe; suite green.
4. **Auto-compaction in the loop** → `CYCLE 15` (`loop2:`): estimate context before
   each provider call; trigger `maybe_compact` via the strategy registry;
   re-inject system prompt after compaction (anti "governance decay"). Verify: unit
   test forces compaction with a huge fake history; long-run exec probe keeps < budget.

Then `CYCLE loop2-final`: full A1–A20 re-sweep + BUILD_REPORT loop-2 section.
