# Critic report — C91 enforced stop + research citation rot

**Date:** 2026-09-04 · **Scope:** HEAD `2de107c`, suite **690 passed / 5
skipped** (green). These are correctness gaps the suite structurally cannot
see, not test failures.

---

## F1 — the C91 evidence cap does not discriminate: false stops (HIGH)

**Evidence.** `src/codemonkey/loop.py:619`

```python
if (not ok and recovery_tracker.advisory_turn is not None
        and _turn_no > recovery_tracker.advisory_turn):
    _post_advisory_failed = True
```

**Any** failed outcome after the advisory turn arms the stop. It is never
matched against the `(tool, error_class)` pair the advisory was issued about.
`build/spec.md:103` states the authorized contract as "when the recovery
policy has issued a documented alternative **and a later tool outcome also
failed**" — and the closing text asserts "the policy advisory issued at turn N
was tried and also failed". The code cannot support that claim.

**Reproduced.** Agent is stuck on `write_file` ×3 (advisory at turn 3), then
*obeys* the advisory — switches to `read_file` — and that call misses a path,
the most routine failure in agent exploration:

```
[stuck] write_file failed 3x in a row (tool-error) — nudge appended
[exit 1] error: [Errno 2] No such file or directory: '.../does_not_exist_probe.txt'
GAVE UP (recovery policy enforced stop): the policy advisory issued at turn 3
was tried and also failed at turn 4.
exit code 3 · provider turns used 4 (of 12)
```

The agent did exactly what the policy asked and was terminated for it, with a
trace that misdescribes why. This is the failure mode the evidence cap was
chosen over a turn-count cap to prevent.

**Fix.** Arm only on a failure whose `(tool, error_class)` matches the pair
recorded at `advisory_turn` — or, if a tool switch should still count, require
the *same error_class*. Record the matched pair in the report so the closing
text is checkable.

**Verify probe (F1).** Scenario above → exit 0/1, no `failure_report.gave_up`;
the existing same-call-repeats scenario → still exit 3.

---

## F2 — every policy stop also emits a false `max_turns` error (MEDIUM)

**Evidence.** `loop.py:955` is the **only** `break` in `run_turns` (normal
completion returns at `:365`). The bail after the loop is unconditional:

```python
    # max_turns bail
    if on_event:
        on_event({"type": "error",
                  "message": f"max_turns ({max_turns}) reached without a final answer"})
```

So a stop at turn 4 of 12 emits `error: max_turns (12) reached without a final
answer` — observed in the F1 repro. Exit code is still 3, so the damage is
trace honesty: a consumer reading events sees an error that did not happen, and
it contradicts the gave-up report on the same trace. C91 introduced this by
adding the first `break`.

**Verify probe (F2).** The F1 repro's event list contains no `error` event
whose message matches `max_turns`; a genuine max_turns run still emits it.

---

## F3 — the C91 tests cannot catch F1 (MEDIUM)

**Evidence.** `tests/test_enforced_stop.py`. `FailProv` returns the *same*
denied `write_file` on every turn, so the post-advisory failure is always the
advisory's own pair — the discriminating case never occurs. The negative
control (`RecoverProv`) makes **no tool calls** after turn 3, so it proves only
that a run with no post-advisory activity does not stop. The arm that matters —
*obeys the advisory, switches approach, incurs an unrelated failure* — is absent.

**Verify probe (F3).** A third test with the F1 provider asserting no stop.

---

## F4 — research citation rot is ongoing, not historical (MEDIUM)

**Evidence.** `build/research-loop45.md` (written 2026-09-04 22:00) cites
`truthpass` under the heading **"In-repo evidence (this repo, not literature)"**:

> `claims` + `truthpass` already extract agent claims … The pack is
> composition + chaining, not new extraction machinery.

`truthpass.py` was deleted the same day by cycle 81 (`5ea507f`, R-A pass).
`claims.py` exists; `truthpass.py` does not. The load-bearing claim of R45 —
that loop 45 needs no new extraction machinery — is built on a module its own
arc deleted. `build/research-loop46.md` still carries five dead references
(`lessons_gate` ×4 incl. C1's entire "Fit" argument, `truthpass` ×1).

**Fix.** Re-point both files, recording what was re-pointed rather than editing
silently. Then make the check mechanical: a research file's attachment points
are re-verified against the tree at the moment its cycles are built, and a dead
citation is a blocking finding.

---

## Checked and correct

- **C94 shipped honestly default-OFF.** `config.py:48` still `"verify_command": ""`;
  `discover.py:3` records the ASK decision and the flip-on-the-number rule;
  `14a13e0` recorded the flip as NO with the reason (false-gate unmeasurable,
  endpoint down).
- **C92 shipped suggest-only**, as authorized — no auto-restore path.
- **Exit 3 is recorded in `build/spec.md:103`** with the decision date, and is
  distinct from error 1 / usage 2.
- The duplicate `failure_report.gave_up` in an event sink is **by design** —
  `exec.py:341` re-emits a translated copy carrying `thread_id`.


---

## Status — all four FIXED and verified (2026-09-04)

| Finding | Status | Evidence |
|---|---|---|
| F1 evidence cap does not discriminate | **FIXED** | `RecoveryTracker.note_advisory` / `is_advised_failure` (`recovery.py`); `loop.py` arms only on the advised-against pair; report carries `advised_pair` + `matched_pair`; `build/spec.md` tightened |
| F2 false `max_turns` on policy stop | **FIXED** | `loop.py` bail guarded by `not getattr(last_turn, "gave_up", None)` |
| F3 tests cannot catch F1 | **FIXED** | 4 tests added; the 3 regressions fail against unfixed HEAD `2de107c` (detached worktree, `PYTHONPATH` at HEAD src) and pass on the fix |
| F4 citation rot | **FIXED** | `research-loop45.md` + `research-loop46.md` re-pointed with dated correction blocks; standing rule proposed |

Repro, before and after, same scenario (agent obeys the advisory, switches
tool, takes one missing-path miss):

```
before: exit 3 · 4 turns used of 12 · GAVE UP "…was tried and also failed"
        + error: max_turns (12) reached without a final answer
after:  exit 0 · 5 turns used · no gave_up event · no max_turns error
```

```
uv run pytest -q  → 694 passed, 5 skipped   (was 690/5; +4 new tests)
uv run codemonkey --help → exec review sessions config models  (A18)
```

**Not re-verified live:** the endpoint has been down across this arc
(`10123d1` records connection-refused ×2), so no live `exec --json` probe was
attempted. The scenarios above run the real `run_exec` path in-process with a
scripted provider, which exercises the loop, the sandbox and the exit-code
contract, but is not a live-endpoint probe. Recorded, not claimed as one.
