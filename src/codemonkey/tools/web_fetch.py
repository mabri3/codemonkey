"""web_fetch — bounded GET (60s timeout, 512KB cap) for docs/research.

Returns the response body as text; status >= 400 is an ok=False result so
the model can react instead of the loop crashing.
"""

from __future__ import annotations
import httpx
from .base import ToolResult, _err

TIMEOUT = 60.0
MAX_BYTES = 512 * 1024


def _enabled(ctx) -> bool:
    """web_fetch is config-GATED: default off (spec:90 'config-enabled').

    Convention: ctx.extra['config'] carries the merged config dict when the
    caller has one (exec/resume pass it). No config entry at all (bare unit
    contexts) means the DEFAULTS apply — web_fetch defaults to False.
    """
    cfg = getattr(ctx, "extra", {}).get("config")
    if cfg is None:
        return False
    return bool(cfg.get("web_fetch", False))


def run(args: dict, ctx) -> ToolResult:
    if not _enabled(ctx):
        return ToolResult(
            output="web_fetch is disabled by config (set 'web_fetch: true' to enable); no network request was made",
            ok=False,
        )
    try:
        url = args["url"]
        client = httpx.Client(timeout=TIMEOUT, follow_redirects=True)
        try:
            with client.stream("GET", url) as resp:
                chunks = []
                total = 0
                for chunk in resp.iter_bytes():
                    chunks.append(chunk)
                    total += len(chunk)
                    if total >= MAX_BYTES:
                        break
                body = b"".join(chunks)[:MAX_BYTES]
                truncated = total > MAX_BYTES
                status = resp.status_code
        finally:
            client.close()
        if status >= 400:
            return ToolResult(output=f"HTTP {status}: {body[:500].decode('utf-8', errors='replace')}", ok=False)
        text = body.decode("utf-8", errors="replace")
        if truncated:
            text += "\n[truncated at 512KB]"
        return ToolResult(output=f"HTTP {status} {len(body)} bytes\n\n{text}")
    except Exception as e:
        return _err(e)
