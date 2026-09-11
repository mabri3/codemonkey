# THREAT_MODEL — codemonkey v5.0

What the sandbox and governance layers DO promise, and what they explicitly
do NOT. Read this before running codemonkey unattended on a machine that
matters.

**Refresh at v5.0 (2026-09-11, CYCLE 123):** the compounding-loop surfaces
are now documented — agent-authored persistence (skills, the playbook) is
guarded on BOTH sides of the store. WRITE side: a run marked by
`web_fetch` / shell output / add-dir reads may create neither skills nor
admitted playbook entries (`skill.refused{reason:"tainted"}`). READ side:
the admission gate is METADATA-ONLY (provenance, exit codes, ids — never
the entry's text; the text-blindness twin test is the pin), a tainted
entry is REFUSED at admission with a deliberate, journaled `--override`,
and revocation restores prior prompt bytes exactly. Provenance also
SURVIVES the machinery that rewrites context: every tool outcome carries
attested `tainted`/`taint_sources`, tainted spills keep sidecars so
read-backs attribute `spill`, and compaction records which of its dropped
messages were tainted-derived. The read-path sweep table below names every
injection path that exists, marks the two remaining gaps (delegate child
output; admitted-skill dispatch output), and records that a DENIED read is
honestly clean — nothing was consumed.

**Refresh at v4.0 (2026-09-10, CYCLE loop45-final):** two new surfaces are
documented below — autonomy budgets (loop 44) and evidence packs (loop 45).
The MCP surface and the trust boundary itself were recorded at loop 43
(R43 ASK 2/3, section above), and the version label now follows the release
this document describes rather than the 1.0 that wrote it.

## Trust boundary — decided, not open (R43 ASK 3, 2026-09-10)

The boundary is **the subprocess + sandbox line**, and no new boundary is
authorized. Recorded explicitly so it is not re-asked:

- Everything inside a `codemonkey exec` process is trusted; everything a tool
  reaches (filesystem writes, shell, network) is gated by `sandbox.py`'s policy
  and the approval policy, and nothing else is.
- The caller is trusted — the caller contract constrains what this binary
  promises its caller, not what the caller may ask for.
- **Model output is untrusted INPUT, not a principal.** It is gated by the same
  sandbox as any other tool argument. Loop 49's provenance work therefore
  HARDENS this boundary; it does not create a new one.
- **Explicitly not authorized:** a daemon, a socket, a server, a credential
  broker, or a second execution context. `contract.md` §5 carries the same
  statement; §6 records the MCP *no server* decision on the same grounds.

## Budgets — declared autonomy limits (R44, loop 44)

**Promised.**

1. **Declared budgets are enforced at the boundary.** `turns` / `tokens` /
   `seconds` / `files` declared in config (`budgets:`) or via
   `CODEMONKEY_BUDGET_*` halt the run *before* the limit is crossed — exit
   **4**, `budget.exhausted` on the trace, the honest closing naming
   field/limit/observed, and a resumable job file (`contract.md` §1/§2;
   conformance `budgetlimit` run).
2. **An absent field means UNLIMITED, and the output says so** — ``None`` is
   never reported as zero.
3. **A self-authored rule may narrow a budget and can never raise one.** The
   refusal is returned and recorded, with a break-verified control.

**NOT promised.**

1. **The defaults are uncalibrated.** Nothing here claims the limit you
   declared is the right one for real work — loop 44's named exception is
   exactly that number (revisit with real runs).
2. **`seconds` is wall-clock since run start**, so transport stalls and
   queueing count against it.
3. **Budgets bound a RUNNING loop, not a process.** A `kill -9` bypasses the
   closing exactly like any crash; what survives is state on disk
   (checkpoints, job file), the same as before this capability.

## Evidence packs + hash-chained journal (R45, loop 45)

**Promised.**

1. **Claims cite their evidence.** A pack binds each claim to the journal
   record indexes behind it (a claim with no evidence index is not emitted).
2. **Redaction happens BEFORE hashing** — a secret in a journaled command is
   not sealed into a document whose purpose is to be handed on.
3. **Tamper evidence.** The chain `h_i = sha256(h_{i-1} ‖ canonical(record_i))`
   commits the head to every record: editing, deleting or reordering any
   record breaks verification (`codemonkey evidence verify` → exit 1,
   `internal: BROKEN`).
4. **Verification is two independent checks** — the pack's own bytes AND the
   journal on disk — and it needs **no model endpoint**: a pack is checkable
   where it was not made.

**NOT promised.**

1. **Repo-scale, not standards-track.** Tamper-evident against *casual
   editing*, not against a determined adversary with write access to the
   chain file: the chain is recomputable from edited records — there is no
   external anchor or signature (the standards-track direction is cited in
   `research-loop45.md`).
2. **The chain attests to the RECORDS, not to the world.** It proves no
   record changed after packing; it does not prove the tools told the truth.
3. **Redaction is the loop-16 guarantee** (API-key-shaped material and
   configured needles), not a general secret scrub — sensitive prose the
   user itself supplied can survive into a pack, which then commits to it.

## Promised

1. **Working-directory write containment** — file tools resolve and reject
   paths outside the workdir (and --add-dir additions). Verified by
   tests/test_sandbox.py (13 denial tests, 9 assertion sites).
2. **Lexical shell checks** — shell commands Lei-restricted per sandbox level;
   read-only blocks mutating commands.
3. **Approval policies** — untrusted / on-request / never gate the shell and
   mutating tools before dispatch.
4. **Rule-based permissions** — deny rules are absolute and evaluated before
   the approval gate; ask escalates; allow only pre-approves what the policy
   would gate.
5. **Checkpoints/undo** — every mutating write snapshots prior contents first,
   scoped to the workspace, restorable with `codemonkey undo`.
6. **Secret hygiene** — API keys are referenced by env-var name, never stored;
   the journal stores argument HASHES, not raw arguments; `codemonkey redact`
   scrubs key-shaped strings from durable stores; config printing masks
   secrets (A2).
7. **Audit trail** — the execution journal records intent/outcome per tool
   call with failure classes; `codemonkey journal` renders it.

## NOT promised (documented limitations)

1. **Process-level containment is ABSENT.** The shell tool runs with the
   user's privileges. sandbox-exec is deprecated (apple/containerization#737)
   and no stable cross-platform replacement was adopted for v1.0 — a shell
   command can deliberately escape via absolute paths.
2. **Lexical checks are bypassable** by construction (command substitution,
   base64, scripts written then executed). They are a guardrail, not a
   security boundary. Treat `danger-full-access` as "no sandbox".
3. **Session/job files may contain sensitive text** the user itself put into
   prompts; redaction covers API-key-shaped material only.
4. **Network access is unrestricted** for web_fetch and shell (curl etc.)
   unless the operator controls the environment.
5. **Delegate children inherit privileges** — depth-1 limits fan-out abuse,
   not what a child may do (sandbox applies per child).

## Operator guidance

- Run unattended only inside a machine/container you control, with
  `workspace-write` or `read-only` + permission rules (deny what must never
  run) + `--approval never` ONLY with allowlist rules.
- Keep API keys in env vars referenced by `api_key_env`; run
  `codemonkey redact run` after sharing artifacts.
- Use verify_command (eval-backed corrections) so mutating requests carry a
  machine-checked outcome rather than a model's word (loop 40's repro gate
  labels a patch UNVERIFIED until a pre-failing test passes).
- Declare budgets for unattended runs (config `budgets:` /
  `CODEMONKEY_BUDGET_*`); the run stops at the boundary with exit 4 and a
  resumable job file instead of degrading past it. Remember the defaults are
  uncalibrated — pick numbers you can defend.
- Hand another agent a pack, not the journal: `codemonkey evidence pack
  <thread> --out pack.json` then `codemonkey evidence verify pack.json` —
  and verify it on THEIR machine, where no model endpoint is needed.

## Read-path sweep — injection paths, covered or NAMED (loop49 C117)

Required by `build/research-loop49.md` §threat model: every path by which
content this repo did not author can enter a run, with its status. "Covered"
means the per-record taint field (`outcome.tainted` / `taint_sources`,
attested on every record) names it; "NAMED" means it is a recorded gap, not
an unexamined assumption.

| path | status | detail |
|---|---|---|
| `web_fetch` bodies | COVERED | source `web_fetch`; success-with-text only; per-record since C117 |
| `shell` stdout/stderr | COVERED (coarse) | source `shell` — ANY output text, exit code irrelevant; conservative by design |
| path reads (`read_file`/`list_dir`/`glob`/`search`) resolving outside the primary workspace root **under an operator-granted add-dir** | COVERED | source `outside_read`; success-only (an errored read consumed nothing) |
| the same read WITHOUT an add-dir root | DENIED-BY-SANDBOX | refused before content is consumed ("outside allowed roots"); correctly NOT a source; pinned by test |
| tainted spill read-backs | NAMED, closes in C118 | a spilled untrusted output's pointer re-enters history; the marker round-trip lands in cycle 118 |
| `delegate` / `delegate_batch` child output | NAMED GAP | a child run's text re-enters the parent without inheriting the child's taint; revisit after this arc |
| admitted-skill dispatch output | NAMED GAP | treated as repo-local command output; the C83 admission gate (probe exit code) is the control that exists |
| `repo_map` / `graph_*` / `digest` (repo-internal views) | TRUSTED-POSTURE | repo content is operator-authored; no outside read, no recorded gap |
