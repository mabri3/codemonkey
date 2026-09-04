"""Fork-and-branch execution (R31).

`branch_create(name)` → git worktree add .branches/<name> (isolated FS +
branch); `branch_run` executes an exec prompt with cwd inside that worktree
(delegate-style child); `branch_list` / `branch_diff <name>` for review.
All git plumbing, no server dependency.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _git(workdir: Path, *args: str) -> tuple[int, str]:
    r = subprocess.run(["git", "-C", str(workdir), *args],
                       capture_output=True, text=True, timeout=60)
    return r.returncode, (r.stdout + r.stderr)


def branch_create(workdir, name: str, base: str = "HEAD") -> dict:
    wd = Path(workdir)
    bdir = wd / ".branches" / name
    rc, out = _git(wd, "worktree", "add", "-b", f"branch/{name}",
                   str(bdir), base)
    return {"ok": rc == 0, "path": str(bdir), "detail": out.strip()[:200]}


def branch_list(workdir) -> list[str]:
    rc, out = _git(workdir, "worktree", "list", "--porcelain")
    names = []
    for line in out.splitlines():
        if line.startswith("worktree "):
            p = Path(line[len("worktree "):])
            if p.parent.name == ".branches":
                names.append(p.name)
    return names


def branch_diff(workdir, name: str) -> str:
    rc, out = _git(workdir, "diff", f"branch/{name}...HEAD", "--stat")
    return out.strip()


def branch_remove(workdir, name: str) -> dict:
    rc, out = _git(workdir, "worktree", "remove", f".branches/{name}",
                   "--force")
    return {"ok": rc == 0, "detail": out.strip()[:200]}
