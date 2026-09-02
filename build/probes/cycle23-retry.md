# CYCLE 23 (loop4) — provider retry/backoff: probe record

Date: 2026-09-02

## Unit
`uv run pytest tests/test_retry.py -q` → **19 passed** (probe requires ≥6).
Covers: 429 + `Retry-After: 2` sleeps exactly 2.0s (no jitter); 503 retries with
bounded full-jitter windows (≤0.5 then ≤1.0) then succeeds; 400/404 raise on the
first attempt; `AuthError` never retried (non-stream and stream); tools-parameter
500 raises immediately with `looks_like_tools_rejection` still true (non-stream
and stream); non-tools 500 retried; exhaustion reports the attempt count
(`after N attempts`); jitter bounds; `Retry-After` parsing; **streaming** status
retry (the default exec path); **transport-error** retry + exhaustion; anthropic
529 retry and 400 no-retry; `max_retries` reaching both providers through
`build_provider` (and clamping negatives to 0); `CODEMONKEY_MAX_RETRIES` override.

`uv run pytest -q` → **264 passed**.

## LIVE A9 re-probe (fallback path intact)
Provider: `unblock` (home llama.cpp still unreachable — 192.168.50.113:8080
curl → 000; see Known limitations).

    build/probes/with_unblock.sh uv run codemonkey exec \
      --sandbox workspace-write --approval never \
      "Use the shell tool to run: echo codemonkey_tool_test. Then reply with exactly the command output."

exit 0; stdout:

    codemonkey_tool_test

stderr tail: `[usage] prompt=2414 completion=52` … `[exit None]` …
`[usage] prompt=2474 completion=79` → `[agent] codemonkey_tool_test`.
