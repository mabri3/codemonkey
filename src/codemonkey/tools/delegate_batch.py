"""delegate_batch — parallel fan-out of delegated tasks (loop9, cycle 38).

Runs N `delegate` calls with at most `max_delegates` concurrent workers
(config, default 2 — one local 27B server saturates quickly). Results are
aggregated IN CALL ORDER regardless of completion order; per-task isolation:
one failure does not affect siblings.
"""

from __future__ import annotations

import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .base import ToolResult

_MAX_TASKS = 8


def run(args: dict, ctx) -> ToolResult:
    if os.environ.get("CODEMONKEY_DELEGATE_DEPTH"):
        return ToolResult(
            output="error: delegation depth limit (no nested delegate calls)", ok=False)

    tasks = args.get("tasks") or []
    if not isinstance(tasks, list) or not tasks:
        return ToolResult(output="error: delegate_batch needs a non-empty 'tasks' list", ok=False)
    if len(tasks) > _MAX_TASKS:
        return ToolResult(output=f"error: too many tasks ({len(tasks)} > {_MAX_TASKS})", ok=False)

    from .delegate import run as _delegate_run
    from ..config import load_config

    max_workers = 2
    try:
        cfg = load_config(cwd=None, ignore_user_config=False)
        max_workers = max(1, int((cfg.get("delegate") or {}).get("max_delegates", 2)))
    except Exception:
        pass
    max_workers = min(max_workers, len(tasks))

    def one(idx_task):
        idx, task = idx_task
        if isinstance(task, str):
            task = {"task": task}
        res = _delegate_run(task, ctx)
        return idx, res.ok, res.output

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        outcomes = list(pool.map(one, list(enumerate(tasks))))
    outcomes.sort(key=lambda o: o[0])

    ok_count = sum(1 for _, ok, _ in outcomes if ok)
    lines = []
    for idx, ok, output in outcomes:
        mark = "ok" if ok else "FAIL"
        lines.append(f"[{mark}] task {idx}: {output[:300]}")
    header = f"delegate_batch: {ok_count}/{len(outcomes)} succeeded"
    return ToolResult(output=header + "\n" + "\n".join(lines), ok=ok_count == len(outcomes))
