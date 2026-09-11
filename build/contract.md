# codemonkey caller contract v1 (loop 43, cycle 101)

**Status:** **PUBLISHED AS BINDING — §1 AND §2 ONLY** (R43 ASK 1 decided
2026-09-10). The reason is the reason the whole arc exists: §1 and §2 have
break-verified controls (102F1 envelope, 102F7 wire/internal type coverage,
102F5 real-trace emit break, plus the §1 exit-code probes), so binding them
claims coverage that exists. **§3 has NO coverage probe** — resume, redaction
and output-schema are asserted only in unit tests that can drift from the
binary — so §3 is **ADVISORY-UNTIL-PROBED** and is marked as such at its own
heading. Binding the whole document would have been the ninth instance of the
defect this arc keeps finding: a claim with no control behind it.

**Scope:** `codemonkey exec` runs (the subprocess surface other agents and
CI drive). `review` shares the envelope opportunistically; direct
`run_turns` callers are inside the boundary (unstamped).

## 1. Exit codes — **BINDING**

| Code | Meaning | Caller action |
|---|---|---|
| 0 | run completed; output schema valid (if `--output-schema`) | use stdout |
| 1 | runtime error (transport, provider, tool crash), best-of-N exhausted with no verifier pass, or output-schema validation failed | retry / inspect stderr |
| 2 | usage / config error (`ExecUsageError`: bad flags, unreadable config, not a git repo, unknown resume thread) | fix invocation |
| 3 | gave-up: the run stopped ITSELF by recovery policy (loop39 C91, spec §Safety) | read the closing; resume via checkpoint |
| 4 | **budget breach**: the run halted itself because a declared runtime budget was exhausted (R44 ASK 1) | resume the job file, or re-run with a deliberately raised budget |

Codes are stable across releases; new codes are additive and documented
here first. `undo`/`rollback`/`eval` follow the same 0/1/2 shape (3 and 4
are exec-runs only).

**Code 4 is documented here FIRST, before its implementation** (R44 ASK 1,
2026-09-10: "contract.md gets code 4 BEFORE the implementation cycle, and
102F7's coverage gate covers it"). The implementation is CYCLE 103; the
conformance probe for code 4 lands in that same cycle, so this row is a
specification, not yet a claim about the shipped binary.

## 2. Event envelope (JSONL, `--json` or `event_sink`) — **BINDING**

Every event crossing the exec boundary carries **`v: 1`**
(`events.SCHEMA_V`, stamped at the exec funnel — `exec.emit` +
`exec.on_event`). Compatibility rule: minor versions ADD fields only;
removing/renaming a field or changing its type bumps major and is
announced here. **Removing or renaming a TYPE is likewise a major bump** —
this section is binding (loop43-final, `3bdb346`) and the coverage probe
parses the two lists below rather than a copy of them (102F8). A consumer
MUST ignore unknown fields and MUST reject (`ValueError`) an event whose `v`
it does not understand — the C102 conformance suite pins this with a
deliberate schema break.

**The lists below are the SOURCE OF TRUTH (102F8).** `build/conformance.py`
parses the type names out of the marked regions and asserts **set equality**
against what real runs produce, in both directions: a documented type no run
produces FAILS, and a produced type that is documented nowhere FAILS. The
marker comments are load-bearing — the parser refuses to run without them
rather than silently matching nothing — and the marked regions must contain
**type names only** (with each name's payload notes in braces). The parsed
counts are pinned in `tests/test_conformance.py`.

Core `type`s (stable set; new types are additive). Wire versus internal
(102F7 decision, written not defaulted):

- ON THE WIRE (every binary `--json` run can produce these, under the
  conditions noted after the list):
  <!-- WIRE-TYPES:BEGIN -->
  `thread.started` {thread_id} ·
  `turn.started` {} ·
  `turn.completed` {usage{total_tokens, prompt_tokens, completion_tokens}} ·
  `item.started` · `item.completed` {item{id, type, tool, …}, thread_id} ·
  `verify.started` {command} · `verify.completed` {ok, exit_code} ·
  `plan.started` · `plan.completed` · `plan.rolled_back` {report} ·
  `repro.verdict` {report{verdict}} ·
  `failure_report.gave_up` · `failure_report.consulted` ·
  `failure_report.budget_exhausted` {report} ·
  `budget.exhausted` {field, limit, observed, turn, declared, meaning} ·
  `stuck` {tool, error_class, streak} ·
  `error` {message} · `notice` {message}
  <!-- WIRE-TYPES:END -->
  **Producer conditions:** `verify.started`/`verify.completed` and
  `repro.verdict` need a verifier configured; `plan.*` needs
  `--atomic-plan` (`plan.completed` on success, `plan.rolled_back` on a
  gave-up); `budget.exhausted` needs a declared budget (loop44 C103);
  `failure_report.*` needs the recovery policy to fire; `stuck` is a
  report-only detector (on the wire since loop 39, documented in 102F7) and
  never terminates a run.
- INTERNAL, deliberately not on the wire:
  <!-- INTERNAL-TYPES:BEGIN -->
  `tool.started` {name, args} · `tool.completed` {name, ok, output, error_class?}
  <!-- INTERNAL-TYPES:END -->
  These are the loop's raw per-call feed; `item.*` is their public
  projection (the renderer reads `$ command` / `[edit] path` off items,
  51F5). Forwarding both would put every call on the stream twice.
  Consumers MUST read `item.*`, never `tool.*`; a future change that emits
  raw `tool.*` on stdout breaks this contract, and the coverage probe
  watches for exactly that.

**Two budget events, one character apart — disambiguation (102F8).** These
are different events with different producers, and neither substitutes for
the other:

| event | producer | fires when | payload | effect |
|---|---|---|---|---|
| `failure_report.budget_exhausted` | loop-39 recovery policy | the POST-ERROR turn budget is spent after a first error | `report`, `policy`, `would_save_*` | **report only** — the run continues to its own end |
| `budget.exhausted` | loop-44 C103 declared budget | a budget declared BEFORE the run (`turns`/`tokens`/`seconds`/`files`) is reached or crossed | `field`, `limit`, `observed`, `turn`, `declared`, `meaning` | **halts the run** — exit code 4 |

The payloads are disjoint (`report` vs `field`), and the coverage probe
asserts that disjointness on real streams rather than trusting this table.
**Decision: neither type is renamed.** Renaming a type in a binding document
is a breaking change under this section's own compatibility rule, and the
defect here was documentation, not the API.

Payload rule (102F5): `report` objects nested inside events are PAYLOADS,
not events — they carry no `type` and no `v`. A consumer walking for
objects with `type` must only match envelope level; conformance probes
this on a real trace (no bare `type` inside any `report`).

## 3. Output and resume guarantees — **ADVISORY (UNTIL IT HAS A COVERAGE PROBE)**

**This section is NOT binding.** It is what the code is intended to do, and
what its unit tests assert, but no probe drives the released binary against
these clauses the way §1 and §2 are driven. Treat a caller that depends on a
clause here as depending on an unverified claim. **Closing condition: a
conformance probe per clause — text-mode stdout purity, `--output-last-message`
contents, schema-violation exit 1, resume-continuation, and pre-redaction of
journaled command text — all run against the binary. When those exist, this
heading loses the advisory marker and the clauses move under §1/§2's standing.**

- Text mode: stdout carries ONLY the final response (diagnostics → stderr).
  `--json` mode: stdout carries ONLY the JSONL event stream.
- `--output-schema <file>`: exit 0 implies the final payload validated;
  exit 1 with a schema violation message otherwise.
- Resume: a thread id + journal file + checkpoint group are sufficient to
  continue (`exec resume`); a resumed thread restarts turn numbering but
  never replays another run's writes (31F1 run-scoped idempotency keys).
- Redaction: secret values from provider config never appear in journaled
  command text (96F1 pre-redaction); raw tool args are never journaled
  (hashes only).

## 4. Conformance (C102)

`build/conformance.py` drives the RELEASED BINARY using only this document
(no repo knowledge).

**Offline** (no endpoint, runs anywhere): the seven §1 exit-code probes,
plus `envelope_probe` — `exec --json` against an unreachable endpoint,
which still drives `thread.started` / `turn.started` / `error` through the
funnel, and every one of them is checked against §2. An empty stream on a
non-usage exit FAILS (§3); exit 2 with no events is BLOCKED-with-reason
(no provider on that machine).

**Live** (endpoint required): the SUCCESS-path event set — `item.*` (the
public projection; raw `tool.*` is internal by §2) and a `turn.completed`
carrying usage. Only this reports BLOCKED when the endpoint is down.

**Live, retired with a run (loop43-final, 2026-09-10):** that probe is
ENDPOINT-GATED — it asserts OUR loop's output, not a model's behaviour — so it
is exercised offline against the scripted endpoint by
`build/conformance_with_stub.py` (102F10's method applied to loop 43's own
gate), pinned by `tests/test_conformance_live_stub.py`. Observed result:
`PASS live-exec (4 events, envelope v1)`, `conformance: offline green; live
PASS`, exit 0. **Named residual (not waived as a class): a real model
*choosing* a tool. Closes by: endpoint up, conformance run with no stub.**

**Coverage** (102F7, reworked by 102F8): `type_coverage` in
`build/conformance.py` **parses** §2's two type lists out of this document
(the marked regions) and asserts **set equality** against streams the binary
produced across six offline stub-driven runs (verify pass-with-retry, atomic
gave-up, successful atomic run, max-turns, alternating-failure burn,
declared-budget halt). It FAILS on a documented type no run produces, on a
produced type documented nowhere, if raw `tool.*` appears on the wire, if the
two budget events' payloads are not disjoint, and (C103) if the
declared-budget run does not exit **4**. Enumerate, don't sample — and read
the contract, don't copy it.

A deliberate envelope break (delete `events.stamp`'s `setdefault`) FAILS
the suite. 102F1 corrected the C102 claim: as shipped, the break-control
asserted on dicts and strings written by hand inside the suite, so a binary
emitting `v`-less events stayed 7/7 green. Re-verified against a worktree
with the break applied: `event missing v: 'thread.started'`, 2 failed.

## 5. Trust boundary (R43 ASK 3, decided 2026-09-10)

**No new trust boundary is authorized.** Verbatim: *"no new trust boundary
authorized. The boundary stays the subprocess + sandbox line. Record it
explicitly so it is not re-asked."* Recorded here and in `THREAT_MODEL.md`
so a later cycle does not re-open it as an open question:

- **The boundary is the subprocess + sandbox line.** Everything inside a
  `codemonkey exec` process is trusted; everything a tool reaches —
  filesystem writes, shell, network — is gated by `sandbox.py`'s policy
  (`read-only` / `workspace-write` + `--add-dir` roots) and the approval
  policy, and nothing else is.
- **The caller is trusted.** A subprocess driving this binary owns it; the
  contract above constrains what the binary promises the caller, not what
  the caller may ask for.
- **Model output is untrusted INPUT, not a principal.** It is gated by the
  same sandbox as any other tool argument. This is what makes the loop-49
  provenance work a *hardening* of an existing boundary rather than the
  invention of a new one.
- **Explicitly NOT authorized:** any new privileged surface (a daemon, a
  socket, a server, a credential broker, a second execution context).

## 6. MCP surface (R43 ASK 2, decided 2026-09-10)

**No MCP server is built.** Verbatim: *"NO SERVER. Hold at deferred client,
recorded as a decision, not a deferral-by-default."* This is a decision with
a reason, not an open question: this tool's public surface is the subprocess
contract above, and a server would create a second, wider entry point
(precisely the new trust boundary §5 declines to authorize) with no
demonstrated consumer. A client — codemonkey *consuming* other MCP servers —
stays deferred and unbuilt; it does not widen this binary's attack surface
when it is built, and it is not claimed as existing today.
