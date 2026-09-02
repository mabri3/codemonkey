# Critic Review — Loop 4 (cycles 18–23)

Reviewer: implementation review requested by the user ("review the current
implementation and fix any bugs"). Scope: the loop-4 surface —
`instructions.py`, verify gate + observation budget in `loop.py`, `repomap.py`,
prefix stability in `protocol.py` / `providers/openai.py`, and the in-flight
CYCLE 23 retry work — read against `build/spec.md` and the loop-4 cycle
descriptions in `build/plan.md`. Unit suite re-run: `uv run pytest -q` →
**264 passed, 0 failed**. LIVE A9 re-probe run through the `unblock` provider
(home llama.cpp unreachable: `curl /v1/models` → 000).

Legend: HIGH (a documented behavior is wrong / an acceptance probe is unproven)
· MED (subtly wrong vs its cycle description; probes still pass) · LOW (polish,
no acceptance impact).

## Findings

### Group A — CYCLE 23 in-flight work (found and FIXED before its commit, 16c27bf)

1. **HIGH — src/codemonkey/providers/openai.py:`_request_stream`**
   What: retry was wired into `_request` only. `exec` runs with
   `stream_deltas=True` (exec.py:112), so every ordinary live turn takes
   `_request_stream`, which had no retry at all — the cycle's feature was
   absent from its own primary path.
   Fix (applied): the same policy wraps the streaming status check. Retries are
   deliberately status-only; replaying after tokens were emitted would duplicate
   output.
   Probe: `test_stream_503_is_retried_then_succeeds`,
   `test_stream_tools_500_raises_immediately`, `test_stream_auth_error_not_retried`.

2. **HIGH — src/codemonkey/providers/__init__.py:`build_provider`**
   What: `max_retries` was applied by setting an attribute on the openai branch
   only; the anthropic branch ignored the parameter entirely, so
   `AnthropicProvider` had no retry and no knob.
   Fix (applied): `max_retries` is a constructor parameter on both providers and
   `AnthropicProvider._post` runs the shared policy.
   Probe: `test_max_retries_reaches_both_providers`,
   `test_anthropic_post_retries_on_529`, `test_anthropic_400_not_retried`.

3. **MED — src/codemonkey/providers/openai.py (transport path)**
   What: `httpx.HTTPError` (connection reset, read timeout) raised on the first
   attempt — the most likely flake against a local server was not retried.
   Fix (applied): bounded transport retry under the same `max_retries`.
   Probe: `test_transport_error_is_retried_then_succeeds`,
   `test_transport_error_exhausted_reports_attempts`.

4. **MED — src/codemonkey/loop.py:24 vs src/codemonkey/retry.py**
   What: two independent copies of the tools-rejection regex. If they drift, a
   tools-500 is retried by one classifier while the other still treats it as the
   A9 fallback trigger.
   Fix (applied): `retry.TOOLS_RE` is the single source; `loop.py` imports it.
   Also: a duplicated 3-line block in `config.ENV_MAP`, and the exhaustion error
   now carries the attempt count its plan probe asks for.

### Group B — pre-existing loop-4 defects (fix cycles below)

5. **HIGH — src/codemonkey/loop.py:180, 246, 248, 253**
   What: CYCLE 22 added `prompt_cache` and threaded `cache_prompt=prompt_cache`
   into 3 of the 7 `provider.chat` call sites. The other 4 omit it and therefore
   fall back to the provider default (`True`). One of them (line 180) is the A9
   tools-rejection fallback — i.e. the path EVERY local llama.cpp run takes — so
   `prompt_cache: false` is silently ignored exactly where cycle 22 aimed. The
   three schema-retry sites have the same leak.
   Evidence: `grep -n "provider.chat(" loop.py` → 7 sites; `grep -n cache_prompt
   loop.py` → 3.
   Fix cycle: **22F1**.
   Probe: with `prompt_cache=False`, a mock provider that rejects `tools` records
   `cache_prompt` absent on BOTH the native attempt and the fallback turn; the
   schema-retry turn likewise.

6. **MED — src/codemonkey/loop.py:429**
   What: the `verify.completed` event reports `"exit_code": 0 if v_ok else 1` —
   a fabricated value, not `vr.returncode`. `codemonkey exec --json` is consumed
   by other agents and CI (intent.md: "clean stdout + stable exit codes"), and
   `events.py:66` renders this number to the user. A verify command exiting 7
   is reported as 1.
   Fix cycle: **19F1**.
   Probe: `verify_command="exit 7"` → the `verify.completed` event carries
   `exit_code == 7`; a passing command carries `0`; a timeout carries a
   non-zero, non-fabricated marker.

7. **LOW — src/codemonkey/loop.py:69-78**
   What: `run_turns` carries two stacked string literals. Only the first is the
   docstring; the second — the one documenting the `on_event` contract and
   `all_messages` — is dead code and invisible to `help()`.
   Fix cycle: folded into **22F1**.

## Not findings (checked, correct as written)

- `sandbox.resolve()` calls `Path.resolve()` on both the candidate and the
  roots, so a symlink pointing out of the workspace is rejected. The module
  docstring's claim that containment is "lexical … never follows symlinks" is
  imprecise, but the behavior is the safer of the two.
- The observation-budget ledger keeps eliding once `obs_spent` reaches the
  budget (allowance 0 → marker only). That is the documented per-run semantics,
  not a leak.
- `tools/__init__.dispatch` runs the coarse sandbox gate before every tool, so
  a newly registered tool is policy-checked by default (unknown tools are
  `danger-full-access`-only).
