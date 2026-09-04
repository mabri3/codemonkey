# Critic report — post-R37 closing review (v3.0.0)

**Date:** 2026-09-04 · **Reviewer:** Claude Opus 5 (review gate, AGENTS.md
"Review-gate discipline") · **Baseline:** `4b75dda` (CYCLE R37 FINAL, v3.0.0),
suite 579/579, `build/plan.md` fully checked, no open cycles.

**Scope.** Implementation review of the shipped tree — not a re-litigation of
approved design. Method: full suite (579 passed), whole-package static pass
(`uvx pyflakes src/codemonkey tests`), targeted read of the loop-30..36
modules and their CLI wiring, and a **live repro for every finding below**
before any edit. No finding is filed on a hunch; each one has a reproduced
failure and a regression test in `tests/test_r37_fixes.py`.

**Graph context.** `graphify query "context assembly and memory selection
modules"` returned the pre-loop-35/36 neighborhood only — `learnedctx.py` and
`adaptivemem.py` appear **nowhere** in `graphify-out/graph.json` (finding F6):
the graph is stale relative to HEAD, which is itself an AGENTS.md violation
(§graphify rule 2) and the reason the structural queries in this review had to
fall back to direct reads.

---

## F1 — HIGH — `loop.py:356`: every permission-rule hit crashes a journaled run

**Evidence.** `src/codemonkey/loop.py:356` (pre-fix) journals the rule decision
as `key=jkey + ":rule"`, but `jkey` is first *assigned* at line 464, after the
approval gate. Python therefore binds `jkey` as a local of `_run_one` and the
read at 356 raises `UnboundLocalError` — which is **not** caught by the
enclosing `except ValueError`, so it escapes `_run_one`, escapes `run_turns`,
and kills the run.

**Trigger.** `journal_thread` set (every real `exec` run) **and** a
`permissions.rules` entry matching the call. That is the whole loop-9 / loop-34
enforcement path: the deny/ask rules the framework advertises as its trust
boundary take down the agent instead of gating the call.

**Why it survived 579 tests.** `perm_rules` is passed to `run_turns` by
`exec.py` and by nothing else in the repo — `grep -rn perm_rules tests/` returns
**zero hits**. `permissions.evaluate` is unit-tested in isolation; the wiring
that consumes its verdict never was. The same defect class was already fixed
once at line 527 (comment "35F1"), on the *other* side of the same variable.

**Repro (pre-fix).** `run_turns(prov, "go", ctx, tool_protocol="prompt",
journal_thread="tid", perm_rules=[{"tool": "write_file", "action": "deny"}])`
→ `UnboundLocalError: cannot access local variable 'jkey'`.

**Verify probe.** `uv run pytest -q tests/test_r37_fixes.py -k r37f1` → 3 passed
(deny blocks the write and the run completes; the rule hit reaches the journal
with a real 24-char action key, not a bare `":rule"`; an allow rule still
executes).

**Fix (R37F1).** Compute `jkey` once at the top of `_run_one` (the key is a pure
function of thread/run/turn/index/args, so hoisting it changes no value) and
drop the later re-computation.

---

## F2 — HIGH — `rules_cli.py:25`: `codemonkey rules-compile` raises NameError always

**Evidence.** `current = (cfg.get("permissions") or {}).get("rules") or []`
with no `cfg` in scope anywhere in the module. Every invocation, journal empty
or not, ends in `NameError: name 'cfg' is not defined`.

**Impact.** The user-facing deliverable of loop 34 — the command that turns
recurring journal failures into draft ask-rules — has never run. `tests/
test_compile_rules.py` covers `compile_corrections()` purely and never invokes
the Typer command, so the suite stayed green over a command that cannot start.
`merge_rules` is imported here and never called: the `--apply` path is
print-only by design, so the import is dead.

**Repro (pre-fix).** `uv run codemonkey rules-compile` → traceback, NameError.

**Verify probe.** `uv run codemonkey rules-compile` → exit 0 with
`(no recurring failures over threshold)`; `uv run pytest -q
tests/test_r37_fixes.py -k r37f2` → 1 passed (CliRunner, exit 0, no traceback).

**Fix (R37F2).** Load the effective config the way every other sub-command does
(`load_config(cwd=Path.cwd())`), degrade to "no existing rules" with a stderr
warning if the config is unreadable, drop the dead import.

---

## F3 — MEDIUM — `schema.py:41`: an invalid `--output-schema` crashes instead of exiting 2

**Evidence.** The module is imported as `_js`, but the handler reads
`except jsonschema.JsonSchemaException` — an unbound name *and* a class that
does not exist in the `jsonschema` package. So a schema that fails
`check_schema` raises `NameError` from inside the `except` clause instead of
the `SchemaError` the CLI maps to exit 2.

**Impact.** Breaks the cycle-6 usage-error contract (`SchemaError` → exit 2)
for the one input most likely to be wrong: a hand-written JSON Schema. The
caller sees a traceback and a generic exit code rather than the documented
usage error.

**Repro (pre-fix).** `load_schema_file(<{"type": "not-a-type"}>)` →
`NameError: name 'jsonschema' is not defined`.

**Verify probe.** `uv run pytest -q tests/test_r37_fixes.py -k r37f3` → 1 passed
(`SchemaError` raised, message names the offending keyword).

**Fix (R37F3).** Split the `ImportError` guard from the validation, catch
`_js.exceptions.SchemaError`, and map any other validator explosion to
`SchemaError` as well.

---

## F4 — MEDIUM — `adaptivemem.py:43-56`: duplicate memory lines blow the token budget

**Evidence.** `adaptive_select` ranks with `lines.index(sv[1])` (the *first*
index of the text, so duplicates tie-break identically) and reconstructs the
output with `[ln for ln in lines if ln in kept_set]` — a membership test over
kept **strings**. Any repeated line is therefore emitted once per occurrence
while being charged to the budget once, and the same text is reported in both
the kept output and the `dropped` list.

**Impact.** The module exists to hold memory injection under a ceiling
(loop 35). `adaptive_select(["a b c", "a b c", "x"], token_budget=3)` returned
**6 tokens** — 2× the budget — and reported `"a b c"` as dropped while emitting
it twice. Repeated lines are the normal shape of an append-only memory file, so
this is the expected input, not a corner case.

**Verify probe.** `uv run pytest -q tests/test_r37_fixes.py -k r37f4` → 2 passed
(budget 3 → exactly `["a b c"]`; budget 7 → all three lines, nothing dropped).

**Fix (R37F4).** Rank and keep by **position** (`enumerate`), never by text.

---

## F5 — LOW — `protocol.py:126`: `Optional` annotation with no import

**Evidence.** `_extract_json_object(text: str) -> Optional[str]` with no
`typing` import. Runtime-safe only because `from __future__ import annotations`
defers evaluation; `typing.get_type_hints()` on it raises `NameError`, so any
introspection-based tooling (schema generation, doc builders, runtime
validators) breaks on this module.

**Verify probe.** `uv run pytest -q tests/test_r37_fixes.py -k r37f5` → 1 passed.

**Fix (R37F5).** Import `Optional`.

---

## F6 — MEDIUM (process) — `graphify-out/` is stale relative to HEAD

**Evidence.** `grep -c "learnedctx\|adaptivemem" graphify-out/graph.json` → **0**,
while both modules are committed at HEAD (cycles 72 and 73). AGENTS.md
§graphify rule 2 makes an incremental `graphify . --update` a per-cycle
obligation, and rule 5 makes the refreshed outputs ship in the same commit.
The last two build cycles did not.

**Impact.** Rule 1 ("any question about the codebase is a graphify query
first") is unenforceable against a graph that does not contain the newest
modules — as this review demonstrated when the loop-35/36 query returned the
loop-34-era neighborhood.

**Verify probe.** `graphify . --update` then
`grep -c "learnedctx" graphify-out/graph.json` → ≥ 1.

**Fix (R37F6).** Refresh and commit the graph with this fix cycle.

---

## F7 — HIGH (scope/honesty) — eight of the ten loop-28..36 capabilities are unreachable

**Evidence.** Static reachability check over the shipped tree — for each
loop-28..36 module, "which *source* file imports it?":

| module (loop) | imported by any `src/` file | agent/CLI entry point |
|---|---|---|
| `graphquery.py` (28) | **no** | none — `tools.SPECS` has no `graph_*` tool |
| `grounding.py` (29) | yes (`tools/write_file.py`) | ✅ reachable |
| `certify.py` (30) | **no** | `eval` never calls `sequential_verdict` |
| `branches.py` (31) | **no** | no `branch` sub-command in `--help` |
| `bestofn.py` (32) | **no** | no caller, no flag |
| `rubrics.py` (33) | **no** | `eval` scores without rubrics |
| `compile_rules.py` (34) | yes (`rules_cli.py`) | ✅ (once F2 is fixed) |
| `adaptivemem.py` (35) | **no** | `strategies/memory.py` never consults it |
| `learnedctx.py` (36) | **no** | `instructions.py` assembles by hand |
| `verifyhint.py` (26) | yes (`exec.py`) | ✅ reachable |

Reproduce: `for m in graphquery certify branches bestofn rubrics adaptivemem
learnedctx; do grep -rl "$m" src/codemonkey --include='*.py' | grep -v "/$m.py";
done` → **empty**. And
`python -c "from codemonkey import tools; print(sorted(tools.SPECS))"` →
`delegate, delegate_batch, edit_file, glob, list_dir, read_file, repo_map,
search, shell, update_memory, update_plan, web_fetch, write_file` — no graph
tool, which was loop 28's entire premise ("expose the structural index to the
agent itself").

**Impact.** Each of these modules is correct, documented and unit-tested, and
**none of them can affect a single real run.** `features.html` and the R37
BUILD_REPORT describe them as shipped capabilities of v3.0.0 ("graph query …
certificates, worktrees, best-of-N, rubrics … adaptive memory, learned
context"). By the repo's own standard — SPRINT.md hard rule 5, and arc rule
R-A "measure or delete" — a library with no caller is not a capability, and
describing it as one in a release report is the failure mode that rule exists
to prevent. The two HIGH bugs above (F1, F2) are the same disease in its
milder form: code whose *logic* is tested and whose *entry point* is not.

**Why it happened (structural, not careless).** Every loop-28..36 verify probe
in `build/plan.md` is written against the module's unit tests. None is written
against a user- or agent-visible surface. A probe of the form "`uv run pytest
-q tests/test_bestofn.py` → N passed" is satisfiable without the feature ever
being reachable, and it was satisfied honestly. The defect is in the probe
grammar, not in anyone's diligence.

**Not fixed here — chartered.** Wiring eight capabilities into `exec`, the tool
registry, the strategy registry and the eval harness is eight cycles of design
work that changes tool surface, strategy selection and eval semantics — squarely
"core design" under AGENTS.md §4 (*stop and ask*). It is filed here and it is
the premise of the forward arc: `build/loops-38-45-proposal.md` §B rule **R-I**
("a capability is not shipped until its entry point is exercised") and CYCLE
R38, which discharges this finding first, before any new capability is built.

**Verify probe (for R38, not for this fix cycle).** For each of the seven
unreachable modules: a probe that drives it through `codemonkey exec` or a
`codemonkey` sub-command — not through `pytest` — and asserts an observable
difference in the run (a tool call made, a certificate printed, a rule
enforced, a shorter context, a branch created).

---

## F8 — MEDIUM (process) — `build/CAPABILITY_REGISTER.md` does not exist

**Evidence.** `ls build/CAPABILITY_REGISTER.md` → no such file, while 13
references to it exist across `build/plan.md`, the proposals and `BUILD_LOG.md`,
including R37's own verify probe: "every `build/CAPABILITY_REGISTER.md` row
reads PROVEN-LIVE, UNIT-ONLY with a stated reason, or DEAD — no UNVALIDATED
rows". A probe over a nonexistent file cannot have been evaluated, yet R37 is
ticked and v3.0.0 is tagged.

**Impact.** The register is the arc's release record (rule R-E) and the only
artifact that would have caught F7: every one of the seven unreachable modules
is exactly an "UNIT-ONLY" row. Its absence is why an honest process still
shipped an overstated report.

**Not fixed here — chartered.** Reconstructing the register means re-deciding
PROVEN-LIVE / UNIT-ONLY / DEAD for ~60 capabilities, which is a cycle with a
live sweep attached, not an edit. Assigned to CYCLE R45 (closing acceptance)
with R38 producing the initial rows.

---

## Non-findings (looked at, deliberately not filed)

- `bestofn.best_of_n` leaves the last candidate applied on total failure. That
  is the documented "honest failure" contract (return the failing evidence),
  and the caller owns the checkpoint — behavior, not a defect.
- `certify.m_certificate` is a fixed-n Hoeffding bound, not a time-uniform one,
  so replaying it after every task is anytime-valid only in spirit. The
  docstring already says "Hoeffding-style"; tightening the bound changes the
  loop-30 certificates that loops 32–36 were measured against, so it belongs in
  a chartered cycle with a re-measurement, not in a fix pass. **Carried to the
  loops 38–45 arc** (see `build/loops-38-45-proposal.md`, R-H).
- `rubrics.score_rubric([])` returns `passed=True, score=0.0`. Contradictory on
  its face, but no caller passes an empty rubric, and changing either half
  moves an eval number. Left alone, recorded here.
- Dead locals flagged by pyflakes in `events.py`, `digest.py`, `exec.py`,
  `tools/update_memory.py`, `tools/repo_map.py` and ~20 unused imports: cosmetic,
  no behavior attached. Not worth a cycle; not worth churning the diff.

**Summary: 3 HIGH, 4 MEDIUM, 1 LOW.** F1–F6 are reproduced, fixed in
R37F1–R37F6 and regression-tested (suite 579 → **587 passed**). F7 and F8 are
reproduced and **deliberately not fixed** — both are core-design/process work
that AGENTS.md §4 says to stop and ask about, and both are discharged by the
proposed forward arc (`build/loops-38-45-proposal.md`: R38 wires the orphans,
R45 rebuilds the register). Until R38 lands, the honest statement of v3.0.0 is:
**27 loops of shipped capability plus nine loop-28..36 libraries, two of which
are reachable.**
