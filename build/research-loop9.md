# Loop 9 Research — Governance for Unattended Runs (CYCLE R9)

Date: 2026-09-02 · Method: live web search (2 queries) + the carried R5
core-design mandate. **Both R5 core-design items are folded into this loop per
the user's blanket authorization (2026-09-02).**

## Researched capabilities

### 1. Rule-based command permissions (pre-tool hooks)
- Sources:
  - https://code.claude.com/docs/en/permissions — canonical evaluation order:
    **deny → ask → allow**; first match wins; patterns per tool.
  - https://www.backslash.security/blog/claude-code-security-best-practices —
    allowlists only for 100%-safe commands; deny rules as last line of defense.
  - https://claudedirectory.org/blog/claude-code-permissions-guide —
    where permission rules live (project config) and how they bind to tools.
- Why: our approvals are policy-shaped only. Rules give deterministic
  pre-dispatch control: `deny` (never runs), `ask` (approval gate), `allow`
  (auto-approve) per tool + shell-command pattern. Evaluated BEFORE the
  approval gate, first match wins — the approval policy remains the fallback.
- Cost: 1 cycle. **SELECTED.**

### 2. Subagent delegation (context isolation)
- Sources:
  - https://jacar.es/en/skills-and-subagents-the-agent-reuse-pattern —
    bounded task → isolated execution → synthesized result back.
  - https://piex.dev/en/packages/subagent — context pollution is the problem;
    a fresh agent per bounded task solves it.
  - https://hidekazu-konishi.com/entry/claude_code_subagents_and_orchestration_guide.html —
    parallel fan-out with isolated contexts.
- Why: a `delegate` tool spawning a fresh codemonkey exec (own context, own
  journal thread) and returning only the final result. Reuses the entire
  existing stack (exec path, sandbox, journal) — the "architecture change" is
  one new tool + result plumbing, far smaller than feared because cycles 24-31
  already built the measurement and audit substrate.
- Cost: 1–2 cycles. **SELECTED** (2 cycles: tool + parallel fan-out limits).

### 3. Pre-tool-use hook scripts (user-configurable commands)
- Sources:
  - https://code.claude.com/docs/en/permissions (hooks model), carried from R5.
- Why: rules cover patterns; hooks cover everything else (audit daemons,
  org-specific checks). A `hooks.pre_tool` config running a user command with
  the call JSON on stdin; exit 0 = allow, non-zero = deny with stderr as
  reason. **NOT SELECTED as separate cycle** — the rules engine's structure
  makes adding hooks a config-list extension later; defer to post-loop-10 if
  wanted.

## SELECTED (loop 9 build list)

1. **CYCLE 36 — rule-based permissions**: `permissions.rules` config — ordered
   list of {tool, pattern (glob over shell command or path), action:
   allow|deny|ask}; evaluated deny→ask→allow, first match wins, before the
   approval gate; journal records rule hits.
   verify: unit (≥6 tests: precedence order, first-match, glob patterns,
   default-ask when no rules, journal hit records, non-shell tools).
2. **CYCLE 37 — delegate tool**: `delegate` tool (task, sandbox) spawning
   `codemonkey exec` as a subprocess with own context + journal thread;
   returns final result text; output capped; delegation depth 1 (no nested
   delegation).
   verify: unit (≥6 tests: subprocess spawn with own thread, result return,
   output cap, depth limit, sandbox inheritance, journal records delegate).
3. **CYCLE 38 — parallel fan-out**: `delegate_batch` accepting a list of
   tasks, running K worker subprocesses (config `max_delegates`, default 2),
   aggregated results in call order.
   verify: unit (≥5 tests: parallel results ordered, per-task isolation
   (failure doesn't kill siblings), max_delegates respected, aggregation shape,
   empty batch).
4. **CYCLE loop9-final — acceptance**: sweep + report.
