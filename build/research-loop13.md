# Loop 13 Research — Learning from the Run History (CYCLE R13)

Date: 2026-09-03 · Method: live web search (2 focused queries) + the shipped
substrate (journal classes, eval baselines, cost ledger, checkpoints,
sessions).

## Researched capabilities

### 1. Lessons extraction from the journal (failure classes → lessons)
- Sources:
  - https://arxiv.org/pdf/2603.10600 — trajectory-informed memory generation:
    mine trajectories for reusable lessons.
  - https://aclanthology.org/2025.acl-long.694.pdf — contextual experience
    replay: environment-specific experiences materially improve later runs.
- Why: the journal holds error_class records (timeout, tool-error, parse…)
  per tool. A `lessons` step aggregates recurring classes into short,
  human-curated-able lesson entries injected via the existing memory channel
  (cycle 7F1) — no new injection path needed.
- Cost: 1 cycle. **SELECTED.**

### 2. Experience retrieval scoped to task relevance
- Sources:
  - https://aclanthology.org/2026.acl-long.27.pdf — memory management study:
    naive always-inject memory causes experience-FOLLOWING (over-applying old
    lessons to new tasks); relevance scoping matters.
- Why: lessons must be tagged (tool, error_class, keywords) and retrieved by
  task-prompt overlap (cycle 27's relevance machinery), not injected wholesale.
- Cost: folded into cycle 45 (retrieval by tag overlap). **SELECTED (folded).**

### 3. Execute-distill-verify (avoid self-confirmation)
- Sources:
  - https://arxiv.org/pdf/2606.24428v1 — single-agent loops that summarize
    their own outcomes entrench mistakes; execute → distill → verify.
- Why: lesson generation must run through the verify gate or be human-curated.
  We auto-generate only STATS (counts) and let the model propose lesson text,
  but lessons only enter injection after `eval --check` passes or explicit
  user editing. **SELECTED as a design constraint on cycle 45** (no separate
  cycle).

### 4. Full self-evolving harness (OPD-Evolver style)
- Sources:
  - https://arxiv.org/pdf/2606.17628 — on-policy distillation evolving the
    whole harness.
- Why: out of scope for a local single-model CLI; requires a training loop.
  **NOT SELECTED.**

### 5. Live in-loop self-improvement (PILOT-style)
- Sources:
  - https://arxiv.org/html/2608.26530v1 — live harness self-update.
- Why: mutating the harness mid-run violates the framework's own governance.
  **NOT SELECTED.**

## SELECTED (loop 13 build list)

1. **CYCLE 45 — lessons store + extraction + scoped retrieval**: `lessons.py`
   (same atomic pattern as jobs): entries {id, tag: {tool, error_class},
   text, source_runs, created}; `lessons extract` mines journal class counts
   into draft lessons (model-curated); retrieval by tag overlap with the task
   prompt into the memory channel; `codemonkey lessons list|add|extract`.
   verify: unit (≥7 tests: extract drafts from journal classes, tag overlap
   retrieval, injection via memory channel, user add, list, no-overlap no-
   inject, atomic writes).
2. **CYCLE 46 — lessons verified-by-eval gate**: a lesson's `verified` flag
   flips only when a golden-suite run with the lesson injected passes its
   baseline check; unverified lessons are excluded from injection.
   verify: unit (≥4 tests: verified flip on green eval, excluded when
   unverified, baseline regression reverts flag, manual verify flag).
3. **CYCLE loop13-final — acceptance**: sweep + report.
