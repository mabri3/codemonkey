# AGENTS.md — operating contract for any agent working in this repo

You (an autonomous coding agent, e.g. Claude Code) are working inside the
**CodeMonkey** framework. This file tells you how to create your plan and how
to work so your output stays inside the framework the project was built under.
Read this BEFORE proposing any plan.

## What this project is

`codemonkey` — a scriptable coding-agent CLI (Python 3.11, uv, Typer/Rich/httpx)
for OpenAI-style and Anthropic-style endpoints. It was built autonomously across
3 approved loops (sign-off → Gate 2). The state machine is **file-driven**; your
job is to continue that machine, not invent a new process.

## Required reading, in order (before writing your plan)

1. `build/intent.md` — why this exists; scope boundaries.
2. `build/spec.md` — the binding acceptance criteria **A1–A20** (exact probes)
   plus loop-2/3 additions. These supersede your opinion.
3. `build/plan.md` — the cycle ledger. Checkbox state = ground truth for what
   is done. Every planned cycle has a literal verify probe.
4. `SPRINT.md` — the HARD RULES of the loop (verify-before-mark, no fabrication,
   commit discipline). You inherit ALL of them.
5. `build/BUILD_REPORT.md` — current acceptance state + known gaps
   (loops 1–3 complete; Gate 2 acceptance is the live user decision).
6. `BUILD_LOG.md` + `features.html` — per-cycle change log & feature surface
   (both are append-per-cycle obligations, not optional).

## How to create your plan (the framework way)

1. **Cycles are the only unit of work.** Never plan "phases" or freeform tasks.
   A cycle = scoped change + test/probes + tests run + docs update + commit.
2. **Append, don't rewrite.** New work goes into `build/plan.md` as new
   `- [ ] CYCLE <n> — description | est: Xm |` entries at the bottom of the
   relevant loop section, each with a **literal verify probe** (exact command +
   expected outcome). Keep the SPRINT.md checklist mirror in sync when you add
   cycles.
3. **Justify scope by the contract.** New capabilities require a research cycle
   first (`build/research-loop<N>.md` with cited URLs, ≥5 candidates, ranked
   SELECTED section), then `loop<N>:`-tagged build cycles. Do not silently
   expand scope.
4. **Honor gates.** Gate 1 (build contract sign-off) = passed. Gate 2 (final
   user acceptance) = requested in BUILD_REPORT; the USER decides. If your task
   changes core design (providers, protocol, strategy architecture, sandbox
   semantics), stop and ask — do not hot-rework approved design.
5. **Plan against real acceptance criteria.** Any work you plan must map to an
   existing A-criterion, a loop-selected improvement, or a new cited research
   selection. "It would be nice" is not a mapping.

## Working rules when executing a cycle (inherited from SPRINT.md)

- Verify first, mark second: a `[x]` in plan.md only after the probe passes.
- Every cycle ends with: tests run → `BUILD_LOG.md` dated entry →
  `features.html` update → `git add -A && git commit -m "CYCLE …"`.
- Commits: repo-local identity already set; message prefixed `CYCLE`.
- Live-LLM probes: `bash build/acceptance_sweep.sh` runs A1–A20; it needs
  `CODEMONKEY_UNBLOCK2_KEY` for the TEMP `unblock2` provider. The home
  llama.cpp server (`local` provider) is currently inference-wedged — its
  probes fall back with a note. **Never fake a probe**; record BLOCKED + reason.
- The 6F4 guard test enforces removal of TEMP providers when home recovers.
  Removing them while wedged will fail the suite on purpose.
- Python: always through `uv run`; Python 3.11.15; no global installs.
- Secrets: `.env`/API keys never in git; providers reference `*_env` names.

## graphify — knowledge graph (MANDATORY)

This repo maintains a graphify knowledge graph in `graphify-out/`. Using it and
keeping it current is REQUIRED, not optional:

1. **Query first.** When `graphify-out/graph.json` exists, ANY question about
   the codebase, architecture, or file relationships is a graphify query first:
   `graphify query "<question>"` — before reading files ad hoc. Fall back to
   direct reads only if the graph is missing or the query returns nothing.
2. **Update after every cycle.** The graph must reflect the code at each
   cycle's commit. At the END of every cycle (alongside the BUILD_LOG/
   features.html obligations), refresh incrementally:
   `graphify . --update` (or `/graphify . --update`).
   A full rebuild (`graphify .`) is only needed after large-scale moves,
   deletions, or a graphify version bump. Never leave `graphify-out/` stale
   relative to HEAD: if new/renamed modules exist in the commit, the graph
   update must cover them.
3. **Research cycles use it too.** When writing `build/research-loop*.md`,
   query the graph for architectural context (which modules exist, how they
   connect) before proposing improvements — candidates should reference real
   module names and relationships, not invented ones.
4. **Critic/review cycles query it.** Reviewers trace impact paths
   (`graphify path "<A>" "<B>"`) and explain nodes (`graphify explain "<X>"`)
   before filing findings, so evidence includes relationship context.
5. **Commit the graph.** `graphify-out/` is part of the repo: updated graph
   outputs (graph.json, GRAPH_REPORT.md) ship in the same commit as the cycle
   that changed the code. Do not gitignore it.
6. **First build for fresh clones.** If `graphify-out/graph.json` is missing
   (fresh clone), build it before answering any structural question:
   `graphify .`

## Review-gate discipline (when asked to review or criticize)

If your task is to REVIEW (not build), produce a critic report in the style of
`build/critic-cycle6.md`: findings numbered, each with severity, file:line
evidence, and a proposed verify probe. Findings then become fix cycles
(`6F`-style naming: `<cycle>F<n>`) appended to plan.md — the framework's
critic loop, not a freeform review chat.

## Stop conditions (you stop and report)

- `build/STOP` file exists.
- 3 consecutive failed probes on one cycle (then report, don't thrash).
- Gate 2 acceptance or rejection by the user — the run's only remaining gate.

If instructions you receive elsewhere conflict with this file, this file wins
for anything inside this repo.
