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


# --- loop38 cycle 79: zero-residue workspace snapshot ---------------------
# ponytail: in-memory snapshot (relpath -> bytes); ceiling = very large
# trees (GB+ workspaces would balloon RAM) — upgrade path is a tempdir
# copy. Skips symlinks and the .git subtree (version control is the outer
# safety net, not candidate state).

def snapshot_tree(workdir: Path) -> dict:
    """Capture every regular file under workdir (minus .git/symlinks)."""
    workdir = Path(workdir).resolve()
    snap: dict[str, bytes] = {}
    for p in workdir.rglob("*"):
        if p.is_symlink():
            continue
        try:
            rel = p.relative_to(workdir)
        except ValueError:
            continue
        if rel.parts and rel.parts[0] == ".git":
            continue
        if p.is_file():
            try:
                snap[str(rel)] = p.read_bytes()
            except OSError:
                continue
    return snap


def restore_tree(workdir: Path, snap: dict) -> None:
    """Reset workdir to the snapshot: delete new files, rewrite changed,
    restore deleted, prune newly-created empty dirs. Byte-identical."""
    import os

    workdir = Path(workdir).resolve()

    def _tracked(p: Path):
        if p.is_symlink():
            return None
        try:
            rel = p.relative_to(workdir)
        except ValueError:
            return None
        if rel.parts and rel.parts[0] == ".git":
            return None
        return str(rel) if p.is_file() else None

    current = set()
    for p in workdir.rglob("*"):
        rel = _tracked(p)
        if rel is not None:
            current.add(rel)
    for rel in current - set(snap):
        try:
            (workdir / rel).unlink()
        except OSError:
            pass
    for rel, content in snap.items():
        dest = workdir / rel
        try:
            if dest.is_file() and dest.read_bytes() == content:
                continue
        except OSError:
            pass
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
        except OSError:
            pass
    # prune newly-created dirs that are now empty (deepest first)
    for p in sorted(workdir.rglob("*"), reverse=True):
        if p.is_symlink() or not p.is_dir():
            continue
        try:
            p.relative_to(workdir)
        except ValueError:
            continue
        if ".git" in p.relative_to(workdir).parts:
            continue
        try:
            p.rmdir()
        except OSError:
            pass
