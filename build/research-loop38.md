# Loop 38 research — reachability: wire the orphans, prove them at the entry point

**Date:** 2026-09-04 · **Cycle:** R38 (utility arc, `build/loops-38-45-proposal.md` §0/§A/§B)
**Premise:** `build/critic-r37.md` F7 — seven loop-28..36 capability modules are
imported by no source file and cannot affect a real run. **This loop cites
in-repo evidence rather than literature, and says so** (the arc's rule R-I exists
because the literature probes of loops 28..36 were written against unit tests).

## Method — investigation is in-repo (cited, reproducible)

The "published numbers" for this loop are the reproducible states of this tree:

**E1 — the F7 import table** (`build/critic-r37.md` §F7, re-verified at HEAD
`e2b857e` via `build/probes/r38_state.sh`): `graphquery`, `certify`,
`branches`, `bestofn`, `rubrics`, `adaptivemem`, `learnedctx` — **NO-IMPORTER**
in `src/codemonkey`; and
`python -c "from codemonkey import tools; print(sorted(tools.SPECS))"` →
`[delegate, delegate_batch, edit_file, glob, list_dir, read_file, repo_map,
search, shell, update_memory, update_plan, web_fetch, write_file]` — no
`graph_*` tool, which was loop 28's entire premise.

**E2 — the entry points that already exist** (read at HEAD): `exec.run_exec`
wires `memory` (7F1), `repo_map` injection (cycle 27), `project_instructions`
(cycle 18), the verify gate (cycle 19) and `perm_rules` (R37F1) into
`run_turns`; `strategies/__init__.py::DOMAINS` carries compaction / memory /
session_state with env-overridable names (A19 pattern); `cli.py` registers
sub-commands (`undo`, `eval`, `status`, `jobs`, `journal`, `lessons`,
`rules-compile`, …) with `try/except ImportError` guards; `tools/__init__.py`
is a `_MODULES`/`SPECS`/`PARAMS` registry that `prompt_block` advertises and
`dispatch` sandboxes.

**E3 — F8/CAPABILITY_REGISTER.md does not exist** (LS at HEAD); 13 references
to it in plan/proposals/BUILD_LOG, including R37's own verify probe.

External citations are limited to API contract surface (official docs): the
lookup-subcommand pattern (`typer` command registration —
https://typer.tiangolo.com/tutorial/commands/), YAML suite authoring already
used by eval (PyYAML.safe_load semantics — https://pyyaml.org/wiki/PyYAMLDocumentation),
and the sandbox read/write classification already codified in
`src/codemonkey/sandbox.py` (`_READ_TOOLS` / `_WRITE_TOOLS`). No capability
claim in this file rests on an external paper number — per design.

## Candidates (≥5, each with the orphan it reaches and the R-I probe shape)

### C1 — graph tools into the tool registry + HEAD-staleness check + `graph` sub-command
Reaches `graphquery.py`. Add `graph_query` / `graph_path` / `graph_explain`
tool modules (`tools/graph_*.py`) registering in `_MODULES`/`SPECS`/`PARAMS`,
gate read-only in `sandbox.py::_READ_TOOLS`. Discharges loop 28's leftover:
a graph older than HEAD makes the tools say `[stale: ...]` in-band instead of
answering silently. A `codemonkey graph <symbol>` print sub-command gives
callers/tests a no-model entry point.
R-I probe: (a) `uv run codemonkey graph run_turns` prints the real node +
edges from this repo's `graphify-out/`; (b) live `exec --json` where the model
must call `graph_query` — the tool trace contains `graph_query`.

### C2 — fourth strategy domain `context`: `static` (default = current assembly) | `learned`
Reaches `learnedctx.py`. The loop-5 registry gains domain `context` (env
`CODEMONKEY_STRATEGY_CONTEXT`, default `static`); `static` reproduces today's
block assembly byte-for-byte, `learned` feeds the four fragments
(project-context / instructions / memory / repo-map) through
`learnedctx.assemble` under a token budget. A/B-measurable per the charter.
R-I probe: with a recording provider through the REAL `run_turns`,
`strategies.context=learned` + tiny budget selects the task-overlapping
fragment and drops the wide one (observable system-prompt difference);
`codemonkey config` shows the effective strategy (A19 surface).

### C3 — memory strategy `adaptive`
Reaches `adaptivemem.py`. Registered in the memory domain as `adaptive`
(token-budgeted recency-decay selection over `FileMemory`'s file, R37F4-correct).
Default stays `file`. R-I probe: real loop run with a recording provider —
only the budget-selected memory lines appear in the system prompt;
`codemonkey config` lists `adaptive`.

### C4 — eval wired to `certify` (early-stop verdict) — R-H discharged FIRST
Reaches `certify.py`. R-H first: the statistic is a fixed-n Hoeffding bound
replayed over nested prefixes — NOT a confidence sequence — so it is RENAMED
in code (`hoeffding_gate`, verdict carries `kind: "hoeffding-gate"`); eval
`--early-stop` prints the named gate verdict and stops the suite. The R-H
choice (rename, not re-derive) is recorded with its consequence: loop-30
numbers measured under the old name are re-labeled, not re-measured.
R-I probe: live 6-task trivial suite with `--delta 0.2` → the eval output
prints `certificate: ... hoeffding-gate ...` and stops before task 6.

### C5 — rubrics as an eval grader
Reaches `rubrics.py`. Suite tasks may carry `rubric: ["contains: x",
"absent: y", "regex: \\d+"]`; score_rubric composes into task scoring
(`rubric: {steps, passed, score}` in results; task fails if the rubric fails).
R-I probe: golden suite run where a task's stdout check passes but its rubric
fails → results show the rubric verdict driving ok=false.

### C6 — `exec --best-of N` with machine verification + zero-residue candidate isolation
Reaches `bestofn.py`: N full attempts; between attempts the workspace tree is
reset byte-identical to the pre-run snapshot (new full-tree snapshot/restore —
checkpoint groups only cover pre-existing files, so a residue-free reset needs
its own snapshot); the verify command scores each candidate; first pass wins;
honest failure keeps the last evidence. Default OFF (N=1) per R-F (N× tokens);
requires `--verify-command`/config `verify_command` (exit 2 otherwise).
R-I probe: scripted real-exec run where attempt 1 writes a wrong file and
attempt 2 the right one → `bestofn.*` events show 2 attempts and the final
tree carries the verified content; plus byte-identity of the reset.

### C7 — `codemonkey branch` sub-command
Reaches `branches.py`: `branch create|list|diff|remove` over git worktrees in
`.branches/` (git plumbing only). R-I probe: on a scratch repo,
`codemonkey branch create demo` → worktree exists at `.branches/demo` and
`git worktree list` names it; removal restores (no residue).

### C8 (closing) — the register + deletion verdict
R-E: reconstruct `build/CAPABILITY_REGISTER.md`, one row per module in
`src/codemonkey/`: PROVEN-LIVE (entry probe named) / UNIT-ONLY (reason) / DEAD.
R-A armed: any module that cannot earn its entry probe this loop is DELETED and
its row records the deletion. The deletion verdict is mechanical, not vibes.

## Rationale & ranking

- **C1/C2/C3** turn three multipliers live for real runs; C1 additionally
  enforces the graph contract AGENTS.md mandates on humans but never gave the
  agent. Highest expected value, zero design risk (extends approved surfaces).
- **C4** is prerequisite hygiene for every later quality claim (R-H honesty).
- **C5** is small but lets loop 40's test-loop measure generated-test quality.
- **C6** is the arc's quality lever for a weak endpoint (execution-verified
  retries) — shippable only default-OFF per R-F, which is why its ADOPTION
  (rather than its existence) stays a user decision in the final report.
- **C7** is the smallest unblock for loop 41 (worktree isolation is its
  stated primitive).

## SELECTED

All eight are selected — this loop adds no new capability; it wires or deletes
what exists (arc premise). Mapped to `loop38:` build cycles appended to
`build/plan.md` (numbering continues 74+):

| # | Cycle | Modules reached | Entry probe (R-I) |
|---|---|---|---|
| 74 | graph tools + staleness + `graph` sub-command | graphquery | `codemonkey graph run_turns` prints real edges; live exec tool trace shows `graph_query` |
| 75 | strategy domain `context` (static/learned) | learnedctx | real-loop system prompt changes under `CODEMONKEY_STRATEGY_CONTEXT=learned` + budget; config shows it |
| 76 | memory strategy `adaptive` | adaptivemem | real-loop system prompt carries only selected lines; config lists it |
| 77 | eval early-stop + R-H rename | certify | live eval prints a `hoeffding-gate` certificate and stops early |
| 78 | eval rubrics | rubrics | results.json carries rubric verdicts that fail a task |
| 79 | `exec --best-of N` + zero-residue isolation | bestofn | scripted exec run shows 2 attempts, verified tree, byte-identical reset |
| 80 | `codemonkey branch` sub-command | branches | worktree created/removed on a scratch repo via the command |
| 81 | register + deletion verdict (R-A/R-E) | — | register exists; every row PROVEN-LIVE/UNIT-ONLY/DEAD; DEAD rows deleted |

`loop38-final` (82) runs the full acceptance sweep and reports Gate 6.

Consequences declared up front:
- `certify` is rewired ONLY after R-H (rule from the plan): rename ships in
  cycle 77 before any eval wiring.
- `--best-of` ships default-OFF per R-F; making it a default-on or unattended
  default is explicitly **not** decided here and returns to the user.
- The `context` strategy domain extends the approved strategy surface; the
  default behavior (`static`) is byte-identical to today's assembly, and
  compaction semantics are untouched.
- If the live endpoint is down, live-entry probes record BLOCKED+reason per
  SPRINT.md rule 7 — the CLI-surface probes (graph/branch/config) still run.
