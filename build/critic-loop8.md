# Critic Review — loops 5–8 (review gate at the loop-8/9 boundary)

Reviewer: fresh-context critic (review task, AGENTS.md §Review-gate).
Scope: shipped code at `c53b47b` (loops 1–8 complete, loop-9 build cycles
36–38 unbuilt) against `build/spec.md`, `build/plan.md` cycle claims and the
BUILD_LOG entries that assert them.

Read-only baseline re-run before any finding was filed:
`uv run pytest -q` → **335 passed, 4 skipped** (home llama.cpp server down;
the 4 skips are the honest `requires_home` skips). Graph consulted
(`graphify query "…dispatch loop connect journal, slim, spill, approvals and
sandbox"`) for the impact paths below.

Every finding here was reproduced with a runnable probe, not read off the
source. Legend: **HIGH** = a shipped feature does not work at all, or data is
corrupted · **MED** = wrong behavior in a real path, no acceptance probe
covers it · **LOW** = silent no-op, no data loss.

## Findings

1. **HIGH — src/codemonkey/exec.py:466-480 (session persistence)**
   What: `all_msgs = getattr(turn, "all_messages", …)` is the FULL conversation
   (history + this run), and every element is re-appended to the append-only
   session store. On resume the entire prior history is written again, so a
   thread's stored messages grow **exponentially** (2ⁿ) across resumes. In the
   same block the final assistant answer is never persisted at all: the `or`
   fallback that adds it only fires when `all_messages` is absent, and the loop
   never appends the closing assistant message to `messages`.
   Repro (fake provider, temp HOME, 3 runs on one thread):
   `run1 → [user "hello one"]`;
   `run2 → [user "hello one", user "hello one", user "hello two"]`;
   `run3 → 7 messages, still zero assistant turns`.
   Impact: A11/A12 pass (the token word is in a *user* message), so acceptance
   never caught it — but every resumed thread feeds the model duplicated user
   turns and no assistant context, and the store grows without bound.
   Fix cycle: **7F2**. Persist only messages produced by this run, and persist
   the final assistant answer exactly once.

2. **HIGH — src/codemonkey/loop.py:75 vs exec.py:381-402, repl.py:139-151,
   eval.py:165**
   What: `run_turns(..., journal_thread="")` is never given a thread by ANY
   production caller. `grep -rn journal_thread src/` outside loop.py returns
   only `eval.py`'s *read* of `task["_journal_thread"]` — a key nothing sets.
   Impact: the whole loop-7 deliverable (cycle 31 execution journal, cycle 32
   idempotent replay, cycle 33 forensics CLI + eval journal stats) is inert in
   every real `codemonkey exec` / REPL / eval run. `codemonkey journal list`
   shows nothing after a real run; the cycle-31/32/33 tests pass only because
   they call `run_turns` directly with an explicit `journal_thread`.
   Secondary hazard the wiring exposes: `journal.args_key()` is keyed on
   `thread|turn|call_index|args`. Wiring the session thread id in unchanged
   would make a **resumed** run's turn 1 collide with the previous run's turn 1
   and replay a stale "wrote N bytes" outcome without writing anything — the
   cycle-32 replay is meant to de-duplicate a retry *inside* one run, not
   across invocations. The key must be run-scoped.
   Fix cycle: **31F1**. Wire `journal_thread` from exec/REPL/eval, add a
   per-run scope to the idempotency key, and keep the REPL at parity with exec
   on context-limit/compaction while wiring it.

3. **MED — src/codemonkey/tools/edit_file.py:214-263 (`_run_batch`)**
   What: each edit is planned against a FRESH read of its path
   (`_load(path, ctx)` per edit). Two edits on the same file therefore both
   start from the on-disk text, and the write-back loop applies them in order —
   last write wins. The earlier edit is silently discarded and the result still
   says `applied 2 file(s) atomically`.
   Repro: `a.txt = "alpha\nbeta\n"`, edits
   `[{a.txt: alpha→ALPHA}, {a.txt: beta→BETA}]` → result ok,
   file = `"alpha\nBETA\n"` (ALPHA lost).
   Impact: cycle 34's headline claim (atomic multi-edit) is wrong exactly where
   a model most naturally batches — several hunks in one file.
   Fix cycle: **34F1**. Accumulate per path so successive edits compose, and
   report one outcome per file.

4. **MED — src/codemonkey/tools/base.py:44-49 + checkpoints.py:66-69**
   What: `_save()` calls `new_checkpoint()` **per file written**, so one
   logical change spread over N files creates N checkpoint groups, and
   `restore_latest()` restores only the newest one.
   Repro: batch edit touching `a.txt` and `b.txt` → `list_checkpoints()` =
   `[['b.txt'], ['a.txt']]`; `undo` restores `b.txt` only, `a.txt` stays
   modified — a torn undo of an "atomic" edit.
   Fix cycle: **14F1**. One checkpoint group per tool call.

5. **MED — src/codemonkey/checkpoints.py:88-101 + cli.py:220-252 (`undo`)**
   What: checkpoints are global (`~/.codemonkey/checkpoints`) and carry no
   record of the workspace they were taken in; `restore_latest(cwd)` writes the
   stored relative paths under whatever cwd `codemonkey undo` runs in.
   Impact: edit repo A, then run `codemonkey undo` in repo B → A's prior file
   contents are written into B at the same relative paths. Silent cross-repo
   clobber; there is no probe for it.
   Fix cycle: **14F2**. Record the workdir with the group and restore only
   groups taken in the current workspace.

6. **LOW — src/codemonkey/loop.py:426-433 (slim journaling)**
   What: `jkey` is a local of the nested `_run_one()`; the slimming block in
   the outcome loop references it in `run_turns`' own scope, where it is
   unbound. The `except Exception: pass` around the block swallows the
   `NameError`, so the cycle-35 "chars-saved journaled with the outcome"
   record is never written (slimming itself still happens).
   Fix cycle: **35F1**. Return the key with the outcome and journal the
   slim stat from it.

## Not findings (checked, behaving as designed)

- `tool_protocol: auto` HTTP-500 → prompt-protocol fallback (SPRINT rule 8) —
  intact, still covered by `tests/test_retry.py` + A9.
- `shell` allowed at `workspace-write` (6F1) — deliberate, spec:97.
- Lexical-only containment and the documented `shell` cwd-escape gap — a
  standing, documented limitation, and the subject of loop 9's charter; not
  re-filed here.
- `_save()` skipping checkpoints for files under `--add-dir` (relative_to
  raises, caught) — fails soft as documented; noted for a future charter.
