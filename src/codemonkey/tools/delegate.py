"""delegate — spawn an isolated child codemonkey run (loop9, cycle 37).

The delegated task executes via `codemonkey exec` as a SUBPROCESS: fresh
context, fresh journal thread, sandbox inherited from the parent. Returns the
child's final stdout (capped). Delegation depth is 1 — a delegate call inside
a delegated run is refused (env marker CODEMONKEY_DELEGATE_DEPTH).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .base import ToolResult

_MAX_TASK = 8000          # chars of task text accepted
_MAX_RESULT = 4000        # chars of child stdout returned
_TIMEOUT_S = 600


def run(args: dict, ctx) -> ToolResult:
    import os

    if os.environ.get("CODEMONKEY_DELEGATE_DEPTH"):
        return ToolResult(
            output="error: delegation depth limit (no nested delegate calls)", ok=False)

    task = str(args.get("task") or "").strip()
    if not task:
        return ToolResult(output="error: delegate needs a 'task'", ok=False)
    if len(task) > _MAX_TASK:
        return ToolResult(output=f"error: task too long ({len(task)} > {_MAX_TASK})", ok=False)

    sandbox = str(args.get("sandbox") or "workspace-write")
    cmd = ["uv", "run", "codemonkey", "exec", "--ephemeral",
           "--sandbox", sandbox, task]

    env = dict(os.environ)
    env["CODEMONKEY_DELEGATE_DEPTH"] = "1"  # children cannot re-delegate
    env.pop("CODEMONKEY_OBSERVATION_BUDGET", None)  # child gets its own budget
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=_TIMEOUT_S, cwd=str(ctx.workdir), env=env,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(output=f"error: delegate timed out after {_TIMEOUT_S}s", ok=False)
    except OSError as exc:
        return ToolResult(output=f"error: delegate spawn failed: {exc}", ok=False)

    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0:
        tail = (err or out)[-400:]
        return ToolResult(output=f"error: delegate exited {proc.returncode}: {tail}",
                          ok=False)
    # stdout in text mode = final message only (diagnostics on stderr)
    if len(out) > _MAX_RESULT:
        out = out[:_MAX_RESULT] + f"...[delegate result capped at {_MAX_RESULT} chars]"
    meta = {"delegated": True}
    return ToolResult(output=out or "(delegate produced no output)", ok=True, meta=meta)
