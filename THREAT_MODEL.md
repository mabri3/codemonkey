# THREAT_MODEL — codemonkey 1.0

What the sandbox and governance layers DO promise, and what they explicitly
do NOT. Read this before running codemonkey unattended on a machine that
matters.

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
- Use verify_command (eval-backed corrections) so mutating requ...
