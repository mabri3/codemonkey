# Critic Review — Cycle 6 (review gate, cycles 1–6)

Reviewer: fresh-context critic. Scope: accumulated diff `6528806..HEAD` vs
`build/spec.md` for all requirements cycles 1–6 claim to satisfy. Unit suite
re-run read-only: `uv run pytest -q` → **103 passed, 0 failed**. Read-only CLI
probes run: git guard (A8 shape, `-C $TMPDIR`) → exit 2, stderr names "git
repository" + `--skip-git-repo-check` ✔; A13 (`CODEMONKEY_PROVIDER=anthropic
codemonkey config`) → exit 0, shows provider anthropic/protocol anthropic ✔.
No live LLM probes run (out of scope for this gate); cycle 5/6 live-probe
evidence in `build/probes/` was audited instead.

Legend: severity = HIGH (spec violation / acceptance probe would fail or is
unproven) · MED (subtly wrong vs spec; probably passes probes) · LOW
(polish/deviation, no acceptance impact yet).

## Findings

1. **HIGH — src/codemonkey/cli.py:297 (whole `_exec_resume_main` shim)**
   What: The argv pre-parser for `exec resume` only understands
   `--json/-o/--ephemeral/--skip-git-repo-check/--provider/--model`. The spec's
   exec flag list (`--sandbox`, `-a/--ask-for-approval`, `-C/--cd`, `--add-dir`,
   `--max-turns`, `--timeout`, `--output-schema`, `--ignore-user-config`,
   `--dangerously-bypass-approvals-and-…` and per-cycle-5 defaults) silently
   fails on resume: unknown flags are swallowed into the *prompt* positional;
   worse, the call at cli.py:376-386 omits `sandbox` entirely, so a resumed
   run drops the effective sandbox back to the config default and never
   forwards `cwd` (`cd=`) either. `codemonkey exec resume --last --sandbox
   read-only "…"` therefore runs at the DEFAULT sandbox and its prompt becomes
   `"--sandbox read-only …"`. Also duplicated, drift-prone exit handling.
   Fix: flatten resume into a Typer command (make `exec` a group with a default
   no-arg invocation, or use `invoke_without_command=True` + context settings),
   so `resume` reuses the full exec flag set via a shared options decorator;
   pass sandbox/cd/add_dirs/etc. through to `run_exec`.

2. **HIGH — src/codemonkey/sandbox.py:71-72 (`can()`); tools/__init__.py:47-64;
   spec §Safety:96-98; acceptance probes A9 / A17**
   What: `shell` is permitted ONLY at `danger-full-access`; `workspace-write`
   denies it ("shell is not permitted under sandbox 'workspace-write'
   (danger-full-access required)"). The spec's sandbox table says
   workspace-write = "writes inside workdir …, shell allowed per policy", and
   cycle 5/6 supposedly passed live A9 using exactly `--sandbox
   workspace-write --approval never "Use the shell tool …"` per
   build/plan.md:159 — with the committed code that combination returns
   `sandbox-denied` from dispatch, so A9 can only ever pass via the model
   *echoing* `codemonkey_tool_test` without executing anything (no
   `thread.item.started/command_execution` evidence exists in any committed
   probe artifact; build/probes has no cycle-5 tool-loop transcript at all).
   A17's letter passes (tests exist) but the spec's intent — read-only denies
   shell **while** workspace-write allows it "per policy" — is inverted vs
   cycle-3's verify which the build team clearly locked in (tests
   test_sandbox_can_matrix / test_check_denies_shell_workspace_write). One of
   spec or code is wrong; per spec, code is wrong.
   Fix: change `can()`/`check()` so `shell` is allowed at `workspace-write`
   (cwd-bound, approval-gated); update the two denying tests; capture a real
   A9 live transcript (with `--json` showing a `command_execution` item) into
   build/probes/ as ground truth.

3. **HIGH — src/codemonkey/exec.py:240 + loop.py:82; evidence:
   build/probes/cycle5-json.out (2× "turn.started"),
   build/probes/cycle6-zebra.jsonl (2× "turn.started")**
   What: exec.py emits a standalone `{"type":"turn.started"}` before the loop,
   then every loop iteration emits another via on_event, so the committed live
   A6-grade JSONL artifacts contain duplicate consecutive `turn.started` lines.
   The spec's event contract is `thread.started → turn.started → item.* →
   turn.completed` — one opening marker per turn, not a synthetic extra.
   units/tests don't catch it (test_exec only asserts presence).
   Fix: delete the standalone `emit({"type": "turn.started"})` at
   exec.py:240 (the loop already emits it) and update the docstring; strengthen
   test_exec to assert exactly one `turn.started` per `turn.completed`.

4. **MED — src/codemonkey/loop.py:80-228 (schema retry inside the "no calls"
   branch); evidence: build/probes/cycle6-zebra.jsonl (4 user msgs)**
   What: (a) Bounded exactly-once retry — correct — but the retry path emits
   `turn.completed` for the retry WITHOUT a preceding `turn.started`
   (loop.py:178-179), so the JSONL contract is unbalanced whenever a retry
   fires. (b) `turn.all_messages` after a successful/failed retry contains the
   full history INCLUDING the schema `retry_prompt` user message and the
   schema-instruction-appended first user prompt, which exec.py:325-339 then
   persists verbatim into the session — resuming a structured-output thread
   replays stale schema instructions + retry meta-dialogue to the model
   (observed: real thread 317e50eee52c.jsonl contains 2 schema user messages).
   (c) If the retry *provider call* times out/errors it's swallowed to
   `retry = None` and only noticed as exit 1 — acceptable per contract but the
   spec's "one retry on failure" arguably means the retry must actually run.
   Fix: emit `turn.started` before the retry provider call; persist messages
   minus the injected schema instruction / retry housekeeping (or store the
   pre-schema prompt and re-append instructions on final turn); document the
   retry-error path.

5. **MED — src/codemonkey/loop.py:4-11 + sandbox.py / exec.py:165-171; spec
   §Safety:99-102 — approval soft-deny is entirely unimplemented**
   What: Approval mode is threaded (`--approval`, `-a`, `approval:` config →
   `ctx.extra["approval"]`) but NOTHING reads it: no soft-deny notice, no
   tool+how-to-allow stderr line, no auto-approve switch. Under
   `approval: on-request` (the DEFAULT), exec today behaves as
   `approval: never` for sandbox-allowed tools and as a hard-deny-with-
   TOOL_RESULT for the rest. Spec requires: exec-mode denied calls are
   SOFT-denied (stderr notice naming the tool + how to allow, run continues,
   exit 0) with `never` = auto-approve. Currently sandbox-denials land in the
   transcript as `sandbox-denied:` TOOL_RESULTs with no stderr notice. Plan
   assigns this to cycle 8 (`approvals.py`), which is fine *for the review*
   surface, but nothing in cycles 1-6 leaves a seam asserting the default
   `on-request` doesn't leak approvals — flagging so cycle 8 must also add the
   regression test pinning agy semantics (soft-deny + exit 0).
   Fix (cycle 8): implement `approvals.py`, have dispatch consult
   `ctx.extra["approval"]`, stderr notice on deny, unit test
   (exit 0 + notice + run continues).

6. **MED — src/codemonkey/exec.py:198 vs spec:60 — event type strings use
   `thread.item.started/completed`, spec contract names `item.started/
   item.completed`**
   What: spec.md:60 contract line-types are `item.started`/`item.completed`
   (codex-style). Implementation emits `thread.item.started` /
   `thread.item.completed` (events.py:9-10 admits it "keeps" both families but
   actually emits only the `thread.item.*` form). A6's literal check
   (thread.started + turn.completed present) still passes, but any
   codex-compatible consumer keyed on `item.started` sees nothing; and
   `turn.started`/`thread.started` lines lack the promised
   `thread_id`/payload parity (turn.started has no payload at all).
   Fix: either change spec (edit build/spec.md via the normal loop) or emit
   `item.started`/`item.completed`; keep emitted-line shape consistent
   (thread.started{thread_id}, turn.completed{usage}).

7. **MED — tools/web_fetch.py:15-31; spec:90 `web_fetch` "(bounded GET,
   config-enabled)"; config.py:57 `"web_fetch": False`**
   What: `web_fetch` is always callable and does a live GET regardless of the
   `web_fetch: false` config flag — the config gate spec'd as part of the tool
   is not checked anywhere (nor does ToolContext carry the flag). Today
   nothing cares (cycle 8 owns the tool admission per plan), and network GET
   from a read tool isn't catastrophic, but the "config-enabled" half of the
   spec line is unmet. Also the truncation detection at web_fetch.py:22,29 is
   inconsistent (`resp.read()` after already consuming `iter_bytes()`), and
   `p.name.match(file_glob)` in search.py:18 uses str.match (regex) on a
   glob — `*.py` there would be invalid regex, silently mis-filtering in the
   Python fallback (`fnmatch` was meant).
   Fix: gate web_fetch on the config in dispatch (needs ToolContext cfg ref)
   in cycle 8; fix search fallback to `fnmatch.fnmatch(p.name, file_glob)` +
   a regression test.

8. **LOW — plan.md cycle-5 verify:86 (`echo prompt | uv run codemonkey exec -`
   → exit 0) and BUILD_LOG cycle-5 section vs committed artifacts**
   What: plan.md checksum claims a live stdin-dash probe was run green; the
   committed probe artifacts contain no stdin-dash output at all
   (build/probes/ has only cycle5-json.out + cycle5-text.stderr). The unit
   test (test_exec_dash_reads_stdin_as_prompt) covers the behavior with a
   fake provider so the *code path* is proven, but for live ground-truth the
   claim in the checklist is unverifiable from the repo. Same class of gap:
   no committed transcript of the cycle-5 git-guard live probe.
   Fix: re-run and commit the A7/stdin probe output + git-guard probe
   transcript into build/probes/ at the next live-provider window.

9. **LOW — config "layer": DEFAULTS carry a hard-coded
   `providers.unblock` block (config.py:31-42)**
   What: By design (documented TEMPORARY), but it also means every `codemonkey
   config` run — including A2/A13 — emits this extra block, BASE_URL and model
   name included. Two real risks: (a) it'll ship past the recovery of the
   home server since nothing fails if you forget; (b) more subtle —
   `PROVIDER_ENV_PREFIXES` + `resolve_api_key` allow `CODEMONKEY_MODEL` /
   `CODEMONKEY_BASE_URL` etc. to silently target the *active* provider, so a
   user running with CODEMONKEY_PROVIDER=anthropic plus a CODEMONKEY_MODEL set
   for local debugging silently mutates the anthropic provider — that's the
   spec'd `.env` override behavior (fine) but combined with the unblock
   provider makes mis-targeting likelier. Not a correctness bug now; flagging
   the removal reminder with teeth.
   Fix: add a `pytest` that fails if `unblock` exists after
   192.168.50.113:8080 chat completions respond (or a dated TODO + issue),
   then delete the block.

10. **LOW — sessions listing staleness (sessions.py:78-99) +
    `list()` sorts by file mtime but displays meta `updated`**
    What: `meta` is appended on every persistence touch, and
    `SessionStore.list()` uses *file mtime* for ordering but reads `updated`
    from the LAST meta line — both are "now" for fresh writes so the output is
    right, but the file format's `created`/`updated` fields are just two
    `time.time()` calls in the same dict; `created` equals `updated` even for
    a resumed thread (first meta stays, so `created` sortof works, but every
    resume appends ANOTHER meta with a *fresh* `created`). Cosmetic; A12 only
    needs thread_id visible (✔ verified in probe).
    Fix (cycle 7, when strategies/session_state lands): single authoritative
    meta (write-once created, update-on-append updated) in both jsonl and
    sqlite backends + test.

## Verified-clean areas (dictate no finding)

- A1/A2/A3/A13 config probes pass live; sanitization masks `api_key` values
  and `sk-`-shaped strings, keeps `_env` pointers visible; no secrets in repo
  (grep for sk-/AKIA/PRIVATE clean outside test literals; `.env`/`*.key`/
  `*.pem` gitignored).
- Exit codes 0/1/2 wired through CLI wrap (usage → 2, ProviderError → 1,
  AuthError → 2); git guard verified live (exit 2, names flag).
- Stdout purity: text-mode drops thread/turn markers; --json purity locked by
  test asserting every line parses + thread.started first; run-error keeps
  stdout empty (test_run_error_exits_1).
- JSONL session store round-trip, `--ephemeral` skip, resume-uses-persisted-
  messages, and `sessions` listing all covered by tests + A11/A12 live probe
  artifacts (thread 317e50eee52c visible in ~/.codemonkey/sessions/).
- Sandbox lexical containment incl. `..`-reject + add-dir reaching: covered
  (test_sandbox.py matrix + dispatch-level deny tests).
- 9 tools present; edit_file unique-reject; shell timeout; output truncation
  marker; rg-fallback search — all green in 103/103 suite.
- Protocol parser: fenced/unfenced/multi-call/garbage-tolerance, native
  openai extraction incl. bad-JSON preservation, auto-fallback on
  tools-param 500 with in-process per-provider memory — test_protocol.py
  covers all, matches plan intent.
