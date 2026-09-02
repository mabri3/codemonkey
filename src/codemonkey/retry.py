"""Provider retry policy (loop4, cycle 23).

Retry with exponential backoff + FULL JITTER on 429/502/503/504/529, on
transport errors, and on 500s that are NOT the llama.cpp tools-parameter
rejection (that 500 must propagate immediately so `tool_protocol: auto` can
fall back to the prompt protocol). `Retry-After` is honored exactly. 4xx
other than 429, and AuthError, are never retried.

`max_retries` (default 3) counts RETRIES, so up to 1 + max_retries attempts.
This module is the single source of truth for the tools-rejection pattern:
`loop.looks_like_tools_rejection` imports `TOOLS_RE` from here so the
classifier that skips retrying and the classifier that triggers the prompt
fallback can never drift apart.
"""

from __future__ import annotations

import random
import re
import time

RETRYABLE = {429, 500, 502, 503, 504, 529}

TOOLS_RE = re.compile(r"(?i)tools")
_TOOLS_RE = TOOLS_RE  # back-compat alias


def should_retry(status: int, error_text: str) -> bool:
    """True if this HTTP status should be retried (tools-500 excluded)."""
    if status not in RETRYABLE:
        return False
    if status == 500 and TOOLS_RE.search(error_text or ""):
        return False  # tools-parameter rejection: fall back, don't retry
    return True


def sleep_delay(
    attempt: int,
    retry_after: float | None = None,
    base: float = 0.5,
    cap: float = 20.0,
) -> float:
    """Delay before retry `attempt` (1-based). Full jitter over the
    exponential backoff window, honoring Retry-After exactly when present."""
    if retry_after is not None:
        return max(0.0, float(retry_after))
    window = min(cap, base * (2 ** (attempt - 1)))
    return random.uniform(0, window)


def parse_retry_after(value) -> float | None:
    """Retry-After header -> seconds (integer form only; HTTP-date ignored)."""
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def do_sleep(seconds: float) -> None:
    time.sleep(seconds)


# -- driver used by every provider request path ------------------------


def attempts_for(max_retries) -> int:
    """Total attempts (first try + retries) for a `max_retries` setting."""
    try:
        return 1 + max(0, int(max_retries))
    except (TypeError, ValueError):
        return 1


def backoff_http(*, attempt: int, attempts: int, status: int, text: str,
                 headers=None) -> bool:
    """Sleep and return True if this HTTP failure should be retried."""
    if attempt >= attempts or not should_retry(status, text):
        return False
    try:
        raw = (headers or {}).get("Retry-After")
    except AttributeError:
        raw = None
    do_sleep(sleep_delay(attempt, parse_retry_after(raw)))
    return True


def backoff_transport(*, attempt: int, attempts: int) -> bool:
    """Sleep and return True if this transport failure should be retried."""
    if attempt >= attempts:
        return False
    do_sleep(sleep_delay(attempt))
    return True


def annotate(exc, attempt: int):
    """Tag a final error with the attempt count when retries were spent."""
    if attempt <= 1:
        return exc
    cls = type(exc)
    out = cls(f"{exc} (after {attempt} attempts)", getattr(exc, "status", None))
    return out
