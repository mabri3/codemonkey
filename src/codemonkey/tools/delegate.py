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


def _spawn(task_text: str, sandbox: str, ctx) -> dict:
    """One child codemonkey run. Returns {ok, output}."""
    import os as _os

    cmd = ["uv", "run", "codemonkey", "exec", "--ephemeral",
           "--sandbox", sandbox, task_text]
    env = dict(_os.environ)
    env["CODEMONKEY_DELEGATE_DEPTH"] = "1"
    env.pop("CODEMONKEY_OBSERVATION_BUDGET", None)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=_TIMEOUT_S, cwd=str(ctx.workdir), env=env)
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": f"error: delegate timed out after {_TIMEOUT_S}s"}
    except OSError as exc:
        return {"ok": False, "output": f"error: delegate spawn failed: {exc}"}
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0:
        tail = (err or out)[-400:]
        return {"ok": False, "output": f"error: delegate exited {proc.returncode}: {tail}"}
    if len(out) > _MAX_RESULT:
        out = out[:_MAX_RESULT] + f"...[delegate result capped at {_MAX_RESULT} chars]"
    return {"ok": True, "output": out or "(delegate produced no output)"}



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
    review_rounds = int(args.get("review_rounds") or 0)
    if review_rounds < 0 or review_rounds > 5:
        return ToolResult(output="error: review_rounds must be 0..5", ok=False)

    sandbox = str(args.get("sandbox") or "workspace-write")

    # ---- implementer run ----
    framed_task = f"[{role} role] {_ROLE_FRAMINGS[role]}\n\n{task}"
    proc_res = _spawn(framed_task, sandbox, ctx)
    if not proc_res["ok"]:
        return ToolResult(output=proc_res["output"], ok=False,
                          meta={"delegated": True, "role": role})
    out = proc_res["output"]

    # ---- adversarial review rounds (loop11 cycle 41) ----
    rounds_log = []
    for rnd in range(1, review_rounds + 1):
        critic_task = (
            f"[critic role] {_ROLE_FRAMINGS['critic']}\n\n"
            f"Review the result of this task:\n---\n{task}\n---\n"
            f"Implementer's output:\n---\n{out[:2000]}\n---\n"
        )
        critic_res = _spawn(critic_task, "read-only", ctx)
        verdict_text = critic_res["output"]
        if not critic_res["ok"]:
            return ToolResult(output=verdict_text, ok=False,
                              meta={"delegated": True, "role": role,
                                    "review_rounds": rounds_log})
        verdict = "OK" if "VERDICT: OK" in verdict_text else "CHANGES-REQUIRED"
        rounds_log.append({"round": rnd, "verdict": verdict,
                           "findings": verdict_text[:1000]})
        if verdict == "OK":
            break
        # fix round: implementer with the findings
        fix_task = (f"[implementer role] Address these review findings and "
                    f"re-verify:\n---\n{task}\n---\nFINDINGS:\n"
                    f"{verdict_text[:2000]}\n---\nPrevious output:\n{out[:1500]}")
        proc_res = _spawn(fix_task, sandbox, ctx)
        if not proc_res["ok"]:
            return ToolResult(output=proc_res["output"], ok=False,
                              meta={"delegated": True, "role": role,
                                    "review_rounds": rounds_log})
        out = proc_res["output"]

    if len(out) > _MAX_RESULT:
        out = out[:_MAX_RESULT] + f"...[delegate result capped at {_MAX_RESULT} chars]"
    meta = {"delegated": True, "role": role}
    if rounds_log:
        meta["review_rounds"] = rounds_log
        meta["verdict"] = rounds_log[-1]["verdict"]
    return ToolResult(output=out or "(delegate produced no output)", ok=True, meta=meta)

    return ToolResult(output=out or "(delegate produced no output)", ok=True, meta=meta)
