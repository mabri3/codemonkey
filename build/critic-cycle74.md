# Critic report — CYCLE 74 (loop 38, in flight, uncommitted)

**Date:** 2026-09-04 · **Reviewer:** review-gate pass requested by the user
("review the current implementation and fix any bugs") before the loops-46-50
proposal. **Scope:** the uncommitted working tree at HEAD `2575515`:

```
 M src/codemonkey/cli.py            (+60)   `codemonkey graph` sub-command
 M src/codemonkey/sandbox.py        (+1/-1) graph_* added to _READ_TOOLS
 M src/codemonkey/tools/__init__.py (+29)   registry/SPECS/PARAMS entries
?? src/codemonkey/tools/graph.py            the three tool implementations
?? tests/test_graph_tools.py                9 tests
```

**Method.** `graphify query "which modules are unreachable orphans and how do
exec, loop, strategies and lessons connect"` for relationship context, then
direct reads of `tools/__init__.py::dispatch`, `sandbox.py::validate_root`,
`graphquery.py`, and a full-suite run.

**Baseline measurement (reproducible):**

```
uv run pytest -q
→ 4 failed, 592 passed in 93.77s
  tests/test_graph_tools.py::test_graph_query_missing_graph_is_honest
  tests/test_graph_tools.py::test_graph_query_returns_matches_and_edges
  tests/test_graph_tools.py::test_graph_explain
  tests/test_tools.py::test_registry_has_all_thirteen
```

The cycle is **not** in a committable state, and per SPRINT.md's
uncommitted-work rule it must be finished (not discarded) before loop 38
advances. Findings below become cycles `74F1`–`74F6` in `build/plan.md`.

---

## F1 — `graph_path` and `graph_explain` do not exist at runtime (HIGH)

**Evidence.** `src/codemonkey/tools/__init__.py:36-38` maps all three names to
one module object:

```python
"graph_query": graph_mod,
"graph_path": graph_mod,
"graph_explain": graph_mod,
```

and `dispatch` (`src/codemonkey/tools/__init__.py:263`) resolves a tool by
calling `mod.run(args, ctx)` — the *only* entry point it knows. So every one of
the three names executes `graph.run()`, which is the **query** implementation
and hard-requires `symbol` (`tools/graph.py:71-73`). `graph.run_path()` and
`graph.run_explain()` are never called from anywhere: dead code.

Observed:

```
dispatch("graph_explain", {"name": "run_turns"}, ctx)
→ ToolResult(output="error: graph_query needs 'symbol'", ok=False)
```

**Why it is HIGH.** `SPECS` advertises `graph_path` and `graph_explain` to the
model in the prompt block, so the agent will emit calls that can only fail.
This is the *same class of defect* as `critic-r37.md` F7 — a capability that is
declared but unreachable — inside the very cycle chartered to end it. Arc rule
R-I is not satisfied by `graph_query` alone: two of the three tools have no
working entry point.

**Verify probe (74F1).** `uv run python - <<'PY'` driving `dispatch` for all
three names against a fixture graph → each returns `ok=True` with tool-specific
output (`graph_path` prints `path: exec.py -> run_turns -> loop.py`;
`graph_explain` prints the node summary); plus
`uv run codemonkey graph run_turns --to loop.py` → exit 0.

---

## F2 — the tests bypass the real `ToolContext`, so three of them cannot pass (MEDIUM)

**Evidence.** `tests/test_graph_tools.py:47-56` defines a hand-rolled `_Ctx`
with `workdir/sandbox/add_dirs/timeout/extra` and no `resolve()`. Every tool in
this repo reaches the filesystem through `sandbox.validate_root`
(`src/codemonkey/sandbox.py:103-105`), which is exactly
`return ctx.resolve(path)`. The stub therefore raises `AttributeError`, which
`_err` converts into a plausible-looking tool error:

```
error: '_Ctx' object has no attribute 'resolve'
```

The file **already imports the real `ToolContext`** (`tests/test_graph_tools.py:22`)
and never uses it. Two failures are caused purely by the stub; a third (F1) is
masked behind it, which is why the defect was not caught while writing.

**Why it matters beyond the red suite.** A stub that silently diverges from the
sandbox contract means these tests would keep passing if `validate_root` grew a
policy check — the class of "probe tests the mock, not the code" that arc rule
R-I exists to forbid.

**Verify probe (74F2).** `tests/test_graph_tools.py` constructs the real
`ToolContext`; `grep -c "_Ctx" tests/test_graph_tools.py` → 0;
`uv run pytest -q tests/test_graph_tools.py` → exit 0.

---

## F3 — the registry exact-set guard was not updated with the registry (MEDIUM)

**Evidence.** `tests/test_tools.py:326-333` (`test_registry_has_all_thirteen`)
asserts `set(names())` equals a literal 13-name set. Cycle 74 adds three names
and does not touch it:

```
AssertionError: assert {…16 names…} == {…13 names…}
```

The guard is doing its job — it is the repo's tripwire against silently
changing the model-visible tool surface — so this is a *missed obligation*, not
a bad test. It must be updated in the same cycle that changes the surface, and
its name (`…all_thirteen`) is now a lie about its own content.

**Verify probe (74F3).** The guard is renamed to a count-free name, asserts the
16-name set including the three `graph_*` tools, and carries the cycle
attribution comment; `uv run pytest -q tests/test_tools.py` → exit 0.

---

## F4 — the single-file graph layout silently yields an empty graph plus a false `[stale]` (MEDIUM)

**Evidence.** `graphquery.find_graph_dir` has a documented fallback that
returns a **file**, not a directory (`src/codemonkey/graphquery.py:22-24`):

```python
single = Path(workdir) / "graph.json"
if single.is_file():
    return single
```

Both consumers assume a directory:
`graphquery.load_graph` iterates `graph_dir.rglob("*.json")`
(`graphquery.py:32`), and `tools/graph.py::_check_staleness` iterates
`Path(graph_dir).rglob("*.json")`. `rglob` on a file path yields nothing, so in
that layout the tool reports `[stale: no graph json found]` **and** answers
from an empty graph — i.e. `(no node matches 'x')` for a symbol that is in the
graph.

**Why it matters.** The stale marker exists precisely so a wrong structural
answer is never given silently; here the marker fires for the wrong reason
while the answer is wrong anyway. Honest-absence is a stated contract of this
cycle ("refusing to guess structure without it", `tools/graph.py:79-83`).

**Verify probe (74F4).** A workspace containing only `graph.json` at its root →
`graph_query` returns the node and its edges, and the output contains no
`[stale:` marker; a second case with `graphify-out/` present is unchanged.

---

## F5 — the three tools disagree about what "not found" means (LOW→MEDIUM)

**Evidence.** `graph.run` returns `ToolResult(output="(no node matches 'x')")`
with the dataclass default `ok=True` (`tools/base.py:18`), while
`run_explain` returns `ok=res["ok"]`, i.e. `ok=False`, for the identical
condition (`tools/graph.py:_explain_local` → `"ok": bool(res["matches"])`), and
`run_path` returns `ok=False` for an unresolved endpoint. A miss therefore
reads to the model as success from one tool and failure from another.

**Verify probe (74F5).** A documented rule in `tools/graph.py`'s module
docstring — *a well-formed query that matches nothing is `ok=True` with an
explicit "(no match)" line; only an unusable graph or bad arguments is
`ok=False`* — enforced by one test per tool.

---

## F6 — CLI dead load and undocumented exit codes (LOW)

**Evidence.** In `cli.py::graph`, `graph = graphquery.load_graph(gdir)` is
computed before the `--to` branch and is unused there (`graph_path_lookup`
re-discovers and re-loads the graph itself); the local name also shadows the
command function `graph`. Separately the command exits `1` when a symbol
matches nothing and `2` when there is no graph, and neither is stated in the
`--help` text, so a scripting caller (the intent doc's primary consumer)
cannot distinguish them without reading source.

**Verify probe (74F6).** No unused load on the `--to` path (the loaded graph is
either used or fetched inside the branch that needs it); the docstring states
exit codes 0/1/2; `uv run codemonkey graph nosuchsymbol_zzz; echo $?` → 1 and
`uv run codemonkey graph run_turns; echo $?` → 0 with ≥1 edge printed.

---

## Not findings (checked, correct)

- `sandbox.py::_READ_TOOLS` classification is right: all three tools are pure
  reads, and `can("shell", "read-only")` still returns `False`
  (`tests/test_graph_tools.py::test_unknown_still_denied_readonly` passes).
- `_check_staleness` returns `""` — never a staleness *claim* — when the git
  probe fails or the workspace is not a repo. Correct direction: it does not
  fabricate freshness *or* staleness.
- The BFS in `graph_path_lookup` terminates correctly (`q = []` then `break`
  drains the queue after the target is reached) and respects `max_depth`.
- `PARAMS` uses `from`/`to` for `graph_path`, matching the SPECS line the model
  reads. Consistent (the `a`/`b` aliases in `run_path` are harmless slack).

## Process obligations still open for cycle 74

`BUILD_LOG.md` entry, `features.html` update, `graphify . --update`, and the
commit are all outstanding — expected for an in-flight cycle, listed here so
the fix pass does not close 74 without them. The cycle's own LIVE probe
(`exec --json` tool trace containing `graph_query`) has not been run; if the
endpoint is down it is recorded BLOCKED + reason, never faked.

---

## ⚠️ Status update — re-verified after a concurrent tick (same day)

This repo runs a 5-minute tick worker (SPRINT.md §Ticks). While this report was
being written, that worker advanced cycle 74. Re-verified against the working
tree at the time of this commit:

| Finding | Status | Evidence |
|---|---|---|
| F1 `graph_path`/`graph_explain` unreachable | **FIXED** | `_MODULES` now maps each name to a distinct adapter (`graph_mod.GraphQueryTool` / `GraphPathTool` / `GraphExplainTool`), so `dispatch`'s `mod.run` reaches the right implementation |
| F2 `_Ctx` stub diverges from the sandbox contract | **FIXED** | `tests/test_graph_tools.py:44` — `class _Ctx(ToolContext)`, so `validate_root` → `ctx.resolve` works |
| F3 registry exact-set guard stale | **FIXED** | `tests/test_tools.py` and `tests/test_tool_schema.py` updated for the three new names |
| F4 single-file graph layout | **OPEN** | `tools/graph.py:31` still `rglob`s a path `find_graph_dir` may return as a file (`graphquery.py:22-24`) |
| F5 no-match `ok` inconsistency | **OPEN** | `tools/graph.py:93` (miss → `ok=True`) vs `:200` in `_explain_local` (miss → `ok=False`) |
| F6 CLI dead load + undocumented exit codes | **OPEN** | `cli.py:252` loads the graph before the `--to` branch that does not use it; exits 0/1/2 still unstated in `--help` |

```
uv run pytest -q tests/test_graph_tools.py tests/test_tools.py
→ 39 passed in 1.57s
```

The three fixed findings are recorded here rather than deleted: the baseline
measurement above (4 failed / 592 passed at HEAD `2575515`) is what the review
actually found, and the F1 defect class — a tool advertised in `SPECS` with no
working entry point — is the arc's R-I premise and belongs in the record.
Cycles 74F1–74F3 in `build/plan.md` are marked accordingly; 74F4–74F7 remain
live work.
