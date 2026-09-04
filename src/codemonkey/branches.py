"""Fork-and-branch execution (R31).

`branch_create(name)` → git worktree add .branches/<name> (isolated FS +
branch); `branch_run` executes an exec prompt with cwd inside that worktree
(delegate-style child); `branch_list` / `branch_diff <name>` for review.
All git plumbing, no server dependency.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


_VALID_NAME = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")


def _git(workdir: Path, *args: str) -> tuple[int, str]:
    r = subprocess.run(["git", "-C", str(workdir), *args],
                       capture_output=True, text=True, timeout=60)
    return r.returncode, (r.stdout + r.stderr)


def is_git_repo(workdir) -> bool:
    rc, _ = _git(Path(workdir), "rev-parse", "--git-dir")
    return rc == 0


def _check_name(name: str) -> str:
    """"" → error detail (keeps worktrees inside .branches/)."""
    if not name or any(c not in _VALID_NAME for c in name):
        return (f"invalid branch name {name!r}: use letters, digits, "
                "'.', '_' or '-'")
    return ""


def branch_create(workdir, name: str, base: str = "HEAD") -> dict:
    wd = Path(workdir)
    bad = _check_name(name)
    if bad:
        return {"ok": False, "path": "", "detail": bad}
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
    # HEAD...branch: what the branch introduces on top of the merge base
    # (the reverse direction diffs the base against HEAD — always empty).
    rc, out = _git(workdir, "diff", f"HEAD...branch/{name}", "--stat")
    return out.strip()


def branch_remove(workdir, name: str) -> dict:
    bad = _check_name(name)
    if bad:
        return {"ok": False, "detail": bad}
    rc, out = _git(workdir, "worktree", "remove", f".branches/{name}",
                   "--force")
    detail = out.strip()[:200]
    if rc != 0:
        return {"ok": False, "detail": detail}
    # drop the branch ref too, so list/diff stay honest (best-effort: the
    # worktree removal is the load-bearing half)
    _git(workdir, "branch", "-D", f"branch/{name}")
    return {"ok": True, "detail": detail}
