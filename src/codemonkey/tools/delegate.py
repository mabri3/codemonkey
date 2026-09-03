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

# loop11 cycle 40: CIV role framings (augmentcode.com/guides/coordinator-
# implementor-verifier; arxiv.org/html/2606.20629 — role specialization).
_ROLE_FRAMINGS = {
    "implementer": "You are the implementer: make the requested change work "
                   "end-to-end; run/verify it before finishing.",
    "critic": "You are the critic: review the artifact/diff for correctness, "
              "edge cases, and spec drift. Structure your reply as FINDINGS "
              "(numbered, with file:line evidence) then a final line VERDICT: "
              "OK or VERDICT: CHANGES-REQUIRED.",
    "verifier": "You are the verifier: run the tests/commands that prove the "
                "change works. Report only observed command output and a "
                "final line VERIFIED: yes|no.",
}
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

    role = str(args.get("role") or "implementer").strip().lower()
    if role not in _ROLE_FRAMINGS:
        return ToolResult(output=f"error: unknown role '{role}' (implementer|critic|verifier)", ok=False)

    framed_task = f"[{role} role] {_ROLE_FRAMINGS[role]}\n\n{task}"
    sandbox = str(args.get("sandbox") or "workspace-write")
    cmd = ["uv", "run", "codemonkey", "exec", "--ephemeral",
           "--sandbox", sandbox, framed_task]

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
    meta = {"delegated": True, "role": role}
    return ToolResult(output=out or "(delegate produced no output)", ok=True, meta=meta)
