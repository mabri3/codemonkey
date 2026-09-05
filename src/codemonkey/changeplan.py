"""Change plans: repository-scale edits that land or roll back whole (loop 41).

C97 (R41 ASK 1+2, decided 2026-09-05): the plan object (C1) with atomic
apply on checkpoint machinery (C3). Ships OFF/opt-in (`--atomic-plan`);
`undo` is untouched — rollback lives under the `rollback` verb.

A plan records, per path, the bytes BEFORE the plan's first write (or the
fact the file did not exist). Rollback restores prior bytes and DELETES
plan-created files — the gap `restore_latest` cannot close (it only
restores snapshots, leaving created files behind as a torn remainder).

Scope, stated (96F1 honesty applies here too): the plan covers writes
through `_save` (write_file/edit_file, incl. edit_file's write-back).
Shell-mediated mutations are NOT rolled back — they are COUNTED
(`shell_calls`) and named in the report as uncovered. A plan report that
hides shell would claim atomicity it does not have (the 91F1 defect
class).

Crash story: the plan persists as plan.json on disk, so a killed run is
recoverable via the `rollback` verb. Automatic rollback fires ONLY on the
run's declared-failure signal (gave_up). max_turns exhaustion does NOT
roll back — the operator may resume, and resume expects files present.
"""

from __future__ import annotations

import json
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

_PLAN_PREFIX = "plan-"


def plans_dir() -> Path:
    from .checkpoints import checkpoints_dir

    d = checkpoints_dir() / "plans"
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class ChangePlan:
    """One atomic unit: id, workspace, per-path prior state."""

    plan_id: str
    workdir: str
    started: float
    group_dir: Path
    files: dict = field(default_factory=dict)  # rel -> {"existed": bool}
    shell_calls: int = 0  # mutations outside _save: counted, not covered


def begin_plan(workdir: Path) -> ChangePlan:
    """Open a plan scope. Plans stack (thread-local); inner rolls back alone."""
    pid = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    group = plans_dir() / f"{_PLAN_PREFIX}{pid}"
    group.mkdir(parents=True, exist_ok=True)
    plan = ChangePlan(plan_id=pid, workdir=str(Path(workdir).resolve()),
                      started=time.time(), group_dir=group)
    _persist(plan)
    _stack().append(plan)
    return plan


def current_plan() -> ChangePlan | None:
    st = _stack()
    return st[-1] if st else None


def end_plan() -> ChangePlan | None:
    """Close the plan scope WITHOUT rolling back. Returns the plan."""
    st = _stack()
    if not st:
        return None
    return st.pop()


def _stack() -> list:
    if not hasattr(_local, "plans"):
        _local.plans = []
    return _local.plans


_local = threading.local()


def _persist(plan: ChangePlan) -> None:
    (plan.group_dir / "plan.json").write_text(json.dumps({
        "plan_id": plan.plan_id, "workdir": plan.workdir,
        "started": plan.started, "files": plan.files,
        "shell_calls": plan.shell_calls,
    }, indent=1))


def note_write(plan: ChangePlan, workdir: Path, rel: str,
               prior: bytes | None) -> None:
    """Record a path's pre-plan state. First-write-wins: the prior that
    matters is the one before the PLAN's first write, not each call's."""
    if rel in plan.files:
        return
    if prior is not None:
        dest = plan.group_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(prior)
    plan.files[rel] = {"existed": prior is not None}
    _persist(plan)


def note_shell(plan: ChangePlan) -> None:
    """A shell call ran inside the plan scope: counted, not covered."""
    plan.shell_calls += 1
    _persist(plan)


def plan_report(plan: ChangePlan) -> dict:
    """The report names what the plan was: id, workspace, files, coverage."""
    return {
        "plan_id": plan.plan_id,
        "workdir": plan.workdir,
        "started": plan.started,
        "files": sorted(plan.files),
        "n_existed": sum(1 for f in plan.files.values() if f["existed"]),
        "n_created": sum(1 for f in plan.files.values() if not f["existed"]),
        "shell_calls_during_plan": plan.shell_calls,
        "shell_covered": False,
    }


def rollback_plan(plan: ChangePlan, workdir: Path) -> dict:
    """Restore the tree to pre-plan bytes. Returns what happened per path.

    14F2 lesson, applied: refuse a workdir mismatch — restoring another
    repo's priors here is how files get clobbered.
    """
    cwd = str(Path(workdir).resolve())
    if cwd != plan.workdir:
        raise ValueError(f"plan {plan.plan_id} belongs to {plan.workdir}, "
                         f"not {cwd}")
    restored, removed, missing = [], [], []
    for rel, meta in plan.files.items():
        dest = Path(cwd) / rel
        if meta["existed"]:
            src = plan.group_dir / rel
            if not src.is_file():
                missing.append(rel)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            restored.append(rel)
        else:
            if dest.exists() and not dest.is_dir():
                dest.unlink()
                removed.append(rel)
            elif dest.is_dir():
                missing.append(f"{rel} (is a directory, left alone)")
            # absent already → nothing to do, not even worth naming
    return {"plan_id": plan.plan_id, "restored": sorted(restored),
            "removed": sorted(removed), "missing": sorted(missing),
            "shell_calls_uncovered": plan.shell_calls}


def load_plan(plan_id: str) -> ChangePlan:
    """Reload a persisted plan (crash recovery for the `rollback` verb)."""
    group = plans_dir() / f"{_PLAN_PREFIX}{plan_id}"
    doc = json.loads((group / "plan.json").read_text())
    plan = ChangePlan(plan_id=doc["plan_id"], workdir=doc["workdir"],
                      started=doc["started"], group_dir=group,
                      files=doc["files"],
                      shell_calls=doc.get("shell_calls", 0))
    return plan


def list_plans() -> list[dict]:
    """Persisted plans, newest first."""
    out = []
    for group in sorted(plans_dir().glob(f"{_PLAN_PREFIX}*"),
                        key=lambda p: p.name, reverse=True):
        try:
            doc = json.loads((group / "plan.json").read_text())
        except OSError:
            continue
        out.append({"plan_id": doc["plan_id"], "workdir": doc["workdir"],
                    "started": doc["started"],
                    "files": len(doc["files"]),
                    "shell_calls": doc.get("shell_calls", 0)})
    return out
