"""Checkpoints / rollback (loop2, cycle 14).

Before any MUTATING tool (write_file / edit_file / shell) touches the
workspace, the touched file's prior contents are snapshotted into
~/.codemonkey/checkpoints/<ts>-<rand>/ preserving the relative path. shell
snapshots can't know what it will touch, so it snapshots nothing but records
a marker; write/edit snapshot their target path.

`codemonkey undo [--list]`: restores the most recent checkpoint (or lists
them). Restore is byte-identical for snapshotted files; files created after
the snapshot that were NOT in it are left alone (git remains the broader
safety net — checkpoints are a fast, targeted undo).

Deletion records: if a mutating tool DELETES a file (shell rm), we can't know
— that risk stays with the sandbox/git. Checkpoints cover the tools with
declared targets (write/edit), which are the autonomous-run workhorses.
"""

from __future__ import annotations

import shutil
import threading
import time
import uuid
from pathlib import Path


def checkpoints_dir() -> Path:
    d = Path.home() / ".codemonkey" / "checkpoints"
    d.mkdir(parents=True, exist_ok=True)
    return d


class Checkpoint:
    """One snapshot group: a directory mirroring touched relative paths."""

    def __init__(self, base: Path):
        self.base = base
        self.base.mkdir(parents=True, exist_ok=True)
        self.manifest = self.base / "manifest.tsv"

    def snapshot_file(self, workdir: Path, rel_path: str, content: bytes) -> None:
        """Store the PRIOR contents of one file (before mutation)."""
        # 14F2: record which workspace this group belongs to, so `undo` in
        # another repo cannot restore these files there.
        marker = self.base / "workdir.txt"
        if not marker.exists():
            marker.write_text(str(Path(workdir).resolve()))
        dest = self.base / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        with self.manifest.open("a") as f:
            f.write(f"{time.time()}\t{rel_path}\t{len(content)}\n")

    def workdir(self) -> str:
        """The workspace this group was taken in ("" for pre-14F2 groups)."""
        marker = self.base / "workdir.txt"
        try:
            return marker.read_text().strip()
        except OSError:
            return ""

    def entries(self) -> list[dict]:
        if not self.manifest.is_file():
            return []
        out = []
        for line in self.manifest.read_text().splitlines():
            parts = line.split("\t")
            if len(parts) == 3:
                out.append({"ts": float(parts[0]), "path": parts[1], "size": int(parts[2])})
        return out


def new_checkpoint() -> Checkpoint:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return Checkpoint(checkpoints_dir() / f"{stamp}-{uuid.uuid4().hex[:6]}")


# 14F1 (critic-loop8 finding 4): a checkpoint used to be opened PER FILE, so
# one logical change spread over N files became N groups and `undo` restored
# only the newest — a torn undo of an "atomic" multi-file edit. Snapshots taken
# during one tool call now share one group. Thread-local because independent
# tool calls in a turn run concurrently (cycle 12) and must not share a group.
_call = threading.local()


def begin_call() -> None:
    """Open a call scope: every snapshot until end_call() shares one group."""
    _call.active = True
    _call.cp = None


def end_call() -> None:
    _call.active = False
    _call.cp = None


def current_checkpoint() -> Checkpoint:
    """The group for the tool call in flight (a fresh one outside any call)."""
    if getattr(_call, "active", False):
        cp = getattr(_call, "cp", None)
        if cp is None:
            cp = new_checkpoint()
            _call.cp = cp
        return cp
    return new_checkpoint()


def list_checkpoints(base: Path | None = None,
                     workdir: Path | str | None = None) -> list[dict]:
    """Checkpoints, newest first: {dir, ts, workdir, files: [rel paths]}.

    `workdir` (14F2) keeps only groups taken in that workspace. Groups written
    before 14F2 carry no workspace record and stay eligible — dropping them
    would silently disable undo for changes made before this cycle.
    """
    root = base or checkpoints_dir()
    if not root.exists():
        return []
    want = str(Path(workdir).resolve()) if workdir is not None else None
    out = []
    for d in root.iterdir():
        if not d.is_dir():
            continue
        cp = Checkpoint(d)
        entries = cp.entries()
        cp_workdir = cp.workdir()
        if want is not None and cp_workdir and cp_workdir != want:
            continue
        if entries:
            out.append({
                "dir": d,
                "ts": max(e["ts"] for e in entries),
                "workdir": cp_workdir,
                "files": [e["path"] for e in entries],
            })
    out.sort(key=lambda c: c["ts"], reverse=True)  # chronological, not name sort
    return out


def restore_latest(workdir: Path, base: Path | None = None) -> dict:
    """Restore the newest checkpoint's files into workdir (byte-identical).

    Only groups taken in `workdir` are eligible (14F2): checkpoints live in one
    global `~/.codemonkey/checkpoints`, and restoring another repo's snapshot
    into this one silently clobbered files at the same relative paths.

    Returns {"restored": [rel, ...], "checkpoint": dir} or raises LookupError.
    """
    cps = list_checkpoints(base, workdir=workdir)
    if not cps:
        raise LookupError("no checkpoints to restore for this workspace")
    cp = cps[0]
    cwd = Path(workdir).resolve()
    for rel in cp["files"]:
        src = Path(cp["dir"]) / rel
        dest = cwd / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    return {"restored": cp["files"], "checkpoint": cp["dir"]}
