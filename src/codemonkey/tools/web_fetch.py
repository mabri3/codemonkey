"""web_fetch — bounded GET (60s timeout, 512KB cap) for docs/research.

Returns the response body as text; status >= 400 is an ok=False result so
the model can react instead of the loop crashing.
"""

from __future__ import annotations
import httpx
from .base import ToolResult, _err

TIMEOUT = 60.0
MAX_BYTES = 512 * 1024


def run(args: dict, ctx) -> ToolResult:
    try:
        url = args["url"]
        client = httpx.Client(timeout=TIMEOUT, follow_redirects=True)
        try:
            with client.stream("GET", url) as resp:
                body = b"".join(resp.iter_bytes())[:MAX_BYTES]
                truncated = resp.status_code == 200 and len(resp.read() if hasattr(resp, 'read') else body) > MAX_BYTES
                status = resp.status_code
        finally:
            client.close()
        if status >= 400:
            return ToolResult(output=f"HTTP {status}: {body[:500].decode('utf-8', errors='replace')}", ok=False)
        text = body.decode("utf-8", errors="replace")
        if len(body) >= MAX_BYTES:
            text += "\n[truncated at 512KB]"
        return ToolResult(output=f"HTTP {status} {len(body)} bytes\n\n{text}")
    except Exception as e:
        return _err(e)
