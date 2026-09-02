"""`codemonkey review` (cycle 8): LLM code review of uncommitted diffs.

Gathers a unified diff (uncommitted changes vs HEAD by default, or vs a base
ref with --base), then runs ONE review turn with the active provider under a
read-only sandbox and a reviewer system prompt.

Exit codes: 0 review produced; 1 provider/turn failure; 2 usage (not a git
repo, no diff, bad ref).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional

REVIEWER_SYSTEM = (
    "You are a meticulous senior code reviewer. You are given a unified diff. "
    "Review it: correctness bugs, security issues, missing tests, error "
    "handling, API misuse, and style. Be concrete — quote the hunk you mean. "
    "End with a verdict line: APPROVE, APPROVE WITH NITS, or CHANGES REQUESTED."
)


def git_out(args: list[str], cwd: Path) -> str:
    r = subprocess.run(["git"] + args, cwd=str(cwd), capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or f"git {args[0]} failed")
    return r.stdout


def gather_diff(cwd: Path, base: Optional[str] = None, *,
                staged: bool = False) -> str:
    """Unified diff context: uncommitted (working tree vs HEAD) or vs base."""
    inside = git_out(["rev-parse", "--is-inside-work-tree"], cwd).strip()
    if inside != "true":
        raise RuntimeError(f"not a git repository: {cwd}")

    if base:
        diff = git_out(["diff", base], cwd)
    elif staged:
        diff = git_out(["diff", "--cached"], cwd)
    else:
        # uncommitted: tracked modifications + staged, plus untracked files listed
        diff = git_out(["diff", "HEAD"], cwd)
        untracked = git_out(["ls-files", "--others", "--exclude-standard"], cwd).strip()
        if untracked:
            listing = "\n".join(f"+ (untracked file, not shown): {u}" for u in untracked.splitlines())
            diff = (diff.rstrip() + "\n\n# untracked files:\n" + listing) if diff else (
                "# untracked files:\n" + listing)
    if not diff.strip():
        raise RuntimeError("no uncommitted changes to review")
    return diff


def run_review(provider, cwd: Path, base: Optional[str] = None, *,
               staged: bool = False, max_chars: int = 48000,
               on_event=None) -> str:
    """Gather the diff and run one review turn. Returns the review text."""
    diff = gather_diff(cwd, base, staged=staged)
    if len(diff) > max_chars:
        diff = diff[:max_chars] + "\n...[diff truncated for review]"

    if on_event:
        on_event({"type": "notice", "message": "review: sending diff for review turn"})
    turn = provider.chat(
        messages=[{
            "role": "user",
            "content": f"Review this unified diff and end with a verdict line.\n\n```diff\n{diff}\n```",
        }],
        system=REVIEWER_SYSTEM,
    )
    review = (turn.content or "").strip()
    if not review:
        raise RuntimeError("reviewer returned an empty review")
    return review
