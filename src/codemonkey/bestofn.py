"""Best-of-N with an execution verifier (R32).

Generate N candidate completions (same prompt, N calls), score each with a
MACHINE check (verify command), keep the first that passes — the model's
self-report is irrelevant. Reuses N-call pattern from delegate_batch and the
verify gate from loop 4. Fallback: if none pass, return the last candidate
plus the failing evidence (honest failure).
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def score_with_verifier(verify_command: str, cwd) -> tuple[bool, str]:
    """Run the machine verifier; (passed, output-tail)."""
    try:
        r = subprocess.run(verify_command, shell=True, cwd=str(cwd),
                           capture_output=True, text=True, timeout=300)
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode == 0, out.strip()[-400:]
    except subprocess.TimeoutExpired:
        return False, "verifier timeout"


def best_of_n(candidates: list[str], *,

              verify_command: str, workdir, apply_fn=None) -> dict:
    """Score candidates in order; pick the first whose application passes
    verify. apply_fn(text) writes the candidate (defaults to identity)."""
    last_fail = ""
    for idx, cand in enumerate(candidates):
        if apply_fn:
            apply_fn(cand)
        ok, tail = score_with_verifier(verify_command, workdir)
        if ok:
            return {"ok": True, "index": idx, "tries": idx + 1,
                    "candidates_scored": idx + 1}
        last_fail = tail
    return {"ok": False, "index": None, "candidates_scored": len(candidates),
            "last_fail_tail": last_fail}
