# codemonkey caller contract v1 (loop 43, cycle 101)

**Status:** SPECIFIED (writing needs no ask). **Publishing this as a
constraint on future loops, and the MCP server/client decision, are R43
ASK 1–3 — explicitly NOT decided here.** `loop43-final` stays HELD.

**Scope:** `codemonkey exec` runs (the subprocess surface other agents and
CI drive). `review` shares the envelope opportunistically; direct
`run_turns` callers are inside the boundary (unstamped).

## 1. Exit codes

| Code | Meaning | Caller action |
|---|---|---|
| 0 | run completed; output schema valid (if `--output-schema`) | use stdout |
| 1 | runtime error (transport, provider, tool crash), best-of-N exhausted with no verifier pass, or output-schema validation failed | retry / inspect stderr |
| 2 | usage / config error (`ExecUsageError`: bad flags, unreadable config, not a git repo, unknown resume thread) | fix invocation |
| 3 | gave-up: the run stopped ITSELF by recovery policy (loop39 C91, spec §Safety) | read the closing; resume via checkpoint |

Codes are stable across releases; new codes are additive and documented
here first. `undo`/`rollback`/`eval` follow the same 0/1/2 shape (3 is
exec-runs only).

## 2. Event envelope (JSONL, `--json` or `event_sink`)

Every event crossing the exec boundary carries **`v: 1`**
(`events.SCHEMA_V`, stamped at the exec funnel — `exec.emit` +
`exec.on_event`). Compatibility rule: minor versions ADD fields only;
removing/renaming a field or changing its type bumps major and is
announced here. A consumer MUST ignore unknown fields and MUST reject
(`ValueError`) an event whose `v` it does not understand — the C102
conformance suite pins this with a deliberate schema break.

Core `type`s (stable set; new types are additive):

- `thread.started` {thread_id} · `turn.started` {} · `turn.completed`
  {usage{total_tokens, prompt_tokens, completion_tokens}}
- `tool.started` {name, args} · `tool.completed` {name, ok, output,
  error_class?} — `error_class` ∈ journal taxonomy (`schema_mismatch`,
  `parse`, `tool-error`, `timeout`, `transport`, …); present only on
  failure.
- `item.started`/`item.completed` {item{id, type, tool, …},
  thread_id} — derived presentation stream for renderers.
- `verify.started` {command} · `verify.completed` {ok, exit_code}
- `plan.started`/`plan.completed`/`plan.rolled_back` {report} (only with
  `--atomic-plan`)
- `repro.verdict` {report{verdict}} (only with a verifier configured)
- `failure_report.gave_up` {report} / `failure_report.consulted` /
  `failure_report.budget_exhausted`
- `error` {message} · `notice` {message}

## 3. Output and resume guarantees

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
(no repo knowledge): offline probes (exit codes, envelope version,
help/version surface) must pass anywhere; live probes (end-to-end exec)
pass where an endpoint is reachable and report BLOCKED otherwise. A
deliberate envelope break (drop `v`) FAILS the suite — shown in C102.
