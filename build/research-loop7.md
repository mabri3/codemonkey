# Loop 7 Research — Reliability & Recovery (CYCLE R7)

Date: 2026-09-02 · Method: live web search (4 queries). Ranking criterion:
leverage for a **local ~27B-class model** in **headless autonomous runs**.

**Core-design note:** the charter flags session-state strategy semantics. This
loop's selections deliberately AVOID changing the session-state strategy
contract — the journal is an append-only sidecar (like cost.json), not a new
session strategy. Blanket user authorization (2026-09-02) covers loops 7-10.

## Researched capabilities

### 1. Write-ahead journal of tool intents/outcomes
- Sources:
  - https://vadim.blog/durable-execution-llm-agents — durable execution =
    the workflow survives crashes; every step journaled before it runs.
  - https://www.reactify-solutions.com/articles/durable-ai-agents-2026 —
    every LLM call, every tool call journaled; resume replays the log.
  - https://zylos.ai/research/2026-04-24-durable-execution-agent-runtimes —
    auditable, resumable calls via checkpoint records.
- Why top: codemonkey already persists CONVERSATIONS (sessions) but not
  EXECUTION INTENT. A tiny append-only `~/.codemonkey/journal/<thread>.jsonl`
  (intent BEFORE dispatch, outcome AFTER) makes runs auditable and enables
  crash forensics ("what was the agent about to do when it died?") without
  touching the session-state strategy contract.
- Cost: 1 cycle. **SELECTED.**

### 2. Idempotency keys for mutating tool calls
- Sources:
  - https://agentspan.ai/blogs/idempotent-tool-calls-safe-retries-for-ai-agents/ —
    idempotency keys + recorded results prevent duplicate side effects.
  - https://www.agentnative.dev/patterns/idempotent-retry-pattern-for-agent-tool-calls —
    a task that started but did not finish may run again on resume; keys make
    that safe.
  - https://learn.agentpatterns.ai/tool-engineering/idempotent-tools/ —
    existence checks where possible; log what can't be made idempotent.
- Why: cycle 23 added transport retries; a retried write_file/edit_file after a
  mid-stream failure could double-apply. Keying mutating calls by
  (thread, turn, call-index) hash and recording results in the journal makes
  retries replay-safe for the file tools.
- Cost: 1 cycle. **SELECTED.**

### 3. Failure taxonomy in the journal (structured classification)
- Sources:
  - https://arxiv.org/html/2603.06847v1 — taxonomy of agentic fault types,
    symptoms, root causes.
  - https://www.mindstudio.ai/blog/ai-agent-failure-pattern-recognition —
    six recurring failure patterns.
- Why: our error events are free-text. Tagging journal outcome records with a
  small enum (transport, auth, timeout, parse, tool-error, budget, unknown)
  turns loops 5-6's honest BLOCKED-slow recordings into queryable data.
- Cost: folded into cycle 31 (same journal write path). **SELECTED (folded).**

### 4. Mid-turn crash resume
- Sources:
  - https://niteagent.com/blog/2026-06-29-durable-ai-agents-temporal-guide —
    resume-from-where for LLM calls and tool executions.
- Why: resume currently works BETWEEN turns (session history). True mid-turn
  resume (replay pending tool calls from the journal) is a bigger lift and
  changes the loop's dispatch flow. **NOT SELECTED this loop** — the journal
  (cycle 31) is its prerequisite; revisit with data.

### 5. Transport reuse (connection pooling)
- Sources:
  - https://www.python-httpx.org/advanced/clients/ — Client reuse gives
  connection pooling + keep-alive; top-level API opens a connection per call.
  - https://ezaiapi.com/blog/ai-api-connection-pooling-performance — TLS
  handshake overhead per call (~80ms+) multiplies across agent turns.
- Why: providers already hold ONE httpx.Client (pooling exists), but the eval
  matrix spawns a fresh provider per task. Confirming/keeping a shared client
  across a run is nearly free. **NOT SELECTED as its own cycle** — verify as
  part of cycle 31's journal work (one client per run is already the case;
  document it).

## SELECTED (loop 7 build list)

1. **CYCLE 31 — execution journal + failure taxonomy**: journal module writes
   `{ts, type: intent|outcome, thread, tool, args-hash, status, error_class,
   duration}` records around every tool dispatch; error_class from a fixed
   enum; `journal tail <thread>` CLI for forensics.
   verify: unit (intent-before-outcome ordering, error classes, hash stability,
   tail command, journal survives crash — kill -9 mid-run); suite green.
2. **CYCLE 32 — idempotent mutating tools**: write_file/edit_file compute an
   idempotency key (thread+turn+call-index+args hash); before dispatch the
   journal is checked for a recorded outcome; on hit the recorded result is
   replayed instead of re-executing.
   verify: unit (key stability, replay-on-hit, no-replay on miss, read-only
   tools unaffected, journal records replay); suite green.
3. **CYCLE 33 — journal forensics + loop-7 probes**: `codemonkey journal`
   command (list/tail/show), failure-class summary per run, eval integration
   (journal stats in results.json).
   verify: unit (CLI shapes, class summary counts); live: a golden-suite run
   produces a journal with class breakdown.
