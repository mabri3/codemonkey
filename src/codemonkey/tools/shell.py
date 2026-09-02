"""shell — run a command via bash in the workspace, bounded by ctx.timeout.

Denied entirely under read-only / workspace-write (see sandbox.can).
Only reachable at danger-full-access. Non-zero exit is ok=False with the
output still returned so the model can read the failure.
"""

from __future__ import annotations
import subprocess
from .base import ToolResult, _err


def run(args: dict, ctx) -> ToolResult:
    try:
        cmd = args["command"]
        p = subprocess.run(
            ["bash", "-lc", cmd],
            capture_output=True,
            text=True,
            cwd=ctx.workdir,
            timeout=ctx.timeout,
        )
        out = (p.stdout or "") + (("\n[stderr] " + p.stderr) if p.stderr else "")
        if not out.strip():
            out = "(no output)"
        if p.returncode != 0:
            return ToolResult(output=f"exit {p.returncode}\n{out}", ok=False)
        return ToolResult(output=out)
    except subprocess.TimeoutExpired:
        return ToolResult(output=f"error: command timed out after {ctx.timeout}s", ok=False)
    except Exception as e:
        return _err(e)
