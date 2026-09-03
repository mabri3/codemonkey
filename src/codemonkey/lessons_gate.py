"""Lessons verified-by-eval gate (loop13, cycle 46).

A lesson's `verified` flag flips true only when a golden-suite eval run with
the lesson injected passes its baseline regression check; a baseline
regression reverts the flag. Unverified lessons are excluded from injection
(experience-following guard). This is the execute-distill-verify constraint
(arxiv 2606.24428) applied to lesson adoption.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .lessons import load_all, mark_verified, save_all


def gate_lesson_with_eval(lesson_id: str, eval_results: dict,
                          baseline_path: Path) -> Optional[dict]:
    """Verify (or revert) a lesson based on an eval run outcome.

    eval_results: the results dict from eval.run_suite.
    baseline_path: the regression-check baseline; a pass_rate drop counts as
    a regression and reverts the lesson to unverified.
    """
    import json

    if not baseline_path.is_file():
        # no baseline to regress against: adopt the lesson only if the run
        # itself was perfect
        ok = eval_results.get("pass_rate", 0) == 1.0
    else:
        base = json.loads(baseline_path.read_text())
        ok = True
        for t in eval_results.get("tasks", []):
            was = (base.get("tasks") or {}).get(t["id"], {}).get("ok")
            if was is True and not t["ok"]:
                ok = False
                break
        if float(base.get("pass_rate", 0)) > eval_results.get("pass_rate", 0):
            ok = False
    return mark_verified(lesson_id, verified=ok)


def injection_entries(task_text: str) -> list[dict]:
    """The injection list: verified lessons scoped to the task."""
    from .lessons import retrieve

    return retrieve(task_text, verified_only=True)
