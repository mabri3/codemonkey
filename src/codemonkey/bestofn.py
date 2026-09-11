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


# --- loop48 cycle 113: the refine seed --------------------------------------
#
# PDR (arXiv 2604.16529) finding this implements: the losers' failure modes are
# the information a first-pass-wins loop discards. The seed below is the
# bounded handoff — one block per failed candidate (index, verifier tail,
# final-message excerpt), total size capped, so the refine prompt grows with
# the CANDIDATE COUNT, never with transcript size.

SEED_HEADER = ("Every candidate attempt above failed its machine check. "
               "Bounded failure evidence:")


def refine_seed(failures: list, *, tail_chars: int = 400,
                text_chars: int = 300, max_chars: int = 4000) -> str:
    """failure records [{index, tail, text}] -> one bounded seed block.
    Deterministic; the truncation is marked, never silent."""
    parts = []
    for f in failures or []:
        tail = " ".join(str(f.get("tail") or "").split())[:tail_chars]
        text = " ".join(str(f.get("text") or "").split())[:text_chars]
        parts.append(f"[candidate {int(f.get('index', 0)) + 1}] "
                     f"verifier said: {tail or '(no tail)'}\n"
                     f"final message: {text or '(empty)'}")
    out = "\n\n".join(parts)
    if len(out) > max_chars:
        out = out[:max_chars] + "\n…(seed truncated — bounds are the point)"
    return out


# --- loop48 cycle 114: the tournament selector (offline, injected) -----------
#
# Tier-2 selection for the case the machine verifier cannot decide: NO
# `--verify-command` and NO config verify command. The structure is a
# round-robin over injected comparisons — the comparison is the OPERATOR's
# (a script, a command) and is MACHINE-CHECKED: only "a", "b" or "equal"
# count as verdicts; anything else refuses the selection with the malformed
# verdict named. Without a comparison the result is the honest empty —
# never a model guess, never a silent pick.
#
# Determinism: pairings run in canonical (input) order, wins are counted,
# ties break toward the LOWER index. For a strict total-order comparison the
# winner is therefore invariant under input permutation (pinned by tests).

VERDICTS = ("a", "b", "equal")


def select_by_tournament(candidates: list, *, compare_fn=None) -> dict:
    """Round-robin tournament over `candidates` (list of dicts with `text`).

    Returns `{"selected": idx|None, "wins": [...], "pairings": n,
    "reason": str, "verdicts": [...]}`. `compare_fn(a_text, b_text)` must
    return "a" | "b" | "equal"; any other return (or a raised exception)
    REFUSES the whole selection (selected None) with the offending pair and
    verdict recorded."""
    n = len(candidates or [])
    texts = [str((c or {}).get("text") or "") for c in (candidates or [])]
    if n == 0:
        return {"selected": None, "wins": [], "pairings": 0,
                "reason": "no candidates", "verdicts": []}
    if compare_fn is None:
        return {"selected": None, "wins": [0] * n, "pairings": 0,
                "reason": "no comparison provided — selection is refused "
                          "rather than guessed", "verdicts": []}
    wins = [0] * n
    verdicts = []
    pairings = 0
    for i in range(n):
        for j in range(i + 1, n):
            pairings += 1
            try:
                v = compare_fn(texts[i], texts[j])
            except Exception as exc:
                return {"selected": None, "wins": wins,
                        "pairings": pairings,
                        "reason": f"comparison raised at ({i},{j}): "
                                  f"{type(exc).__name__}: {exc}",
                        "verdicts": verdicts}
            if v not in VERDICTS:
                return {"selected": None, "wins": wins, "pairings": pairings,
                        "reason": f"malformed verdict at ({i},{j}): {v!r} "
                                  f"(valid: {list(VERDICTS)})",
                        "verdicts": verdicts}
            verdicts.append({"i": i, "j": j, "v": v})
            if v == "a":
                wins[i] += 1
            elif v == "b":
                wins[j] += 1
    best = max(wins)
    selected = wins.index(best)  # ties -> lower index, by construction
    return {"selected": selected, "wins": wins, "pairings": pairings,
            "reason": f"{best} win(s), ties to the lower index",
            "verdicts": verdicts}


def run_compare_cmd(cmd: str, text_a: str, text_b: str, workdir) -> str:
    """Invoke the operator's comparison command on two candidate payloads.

    Each payload is written to a temp file and the command runs with the two
    paths appended (bash -lc); its FIRST stdout line must be one of the valid
    verdicts. Anything else (crash, empty, other text) is returned AS-IS for
    the selector to refuse — this function never guesses."""
    import tempfile

    with tempfile.TemporaryDirectory(prefix="bo-cmp-") as td:
        fa = Path(td) / "a.txt"
        fb = Path(td) / "b.txt"
        fa.write_text(text_a)
        fb.write_text(text_b)
        try:
            r = subprocess.run(["bash", "-lc", f"{cmd} {fa} {fb}"],
                               cwd=str(workdir), capture_output=True,
                               text=True, timeout=120,
                               stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return "comparison command timed out"
        out = (r.stdout or "").strip().splitlines()
        if r.returncode != 0:
            return f"comparison command exit {r.returncode}: {(r.stderr or '').strip()[-160:]}"
        return out[0].strip() if out else ""
