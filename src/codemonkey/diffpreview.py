"""Diff-preview approval mode (R23B).

`--approval preview`: before a mutating dispatch, compute the would-be diff
and surface it; the tool does NOT run in this pass. The model receives the
preview plus instruction to re-issue with approval=never if acceptable —
the operator watches the previewed diff before the next pass executes.
"""

from __future__ import annotations

import difflib
from pathlib import Path


def unified_diff(path: str, before: str, after: str) -> str:
    return "\\n".join(difflib.unified_diff(
        before.splitlines(), after.splitlines(),
        fromfile=f"a/{path}", tofile=f"b/{path}", lineterm=""))


def preview_diff_write(path: str, new_content: str, workdir) -> str:
    p = workdir / path
    before = p.read_text() if p.is_file() else ""
    return unified_diff(path, before, new_content) or "(new file)"


def preview_diff_edit(path: str, old_string: str, new_string: str,
                      workdir, replace_all: bool = False) -> str:
    p = workdir / path
    before = p.read_text() if p.is_file() else ""
    if not before:
        return "(file missing: edit would fail)"
    if replace_all:
        after = before.replace(old_string, new_string)
    else:
        after = before.replace(old_string, new_string, 1)
    if after == before:
        return "(no change: search text not found)"
    return unified_diff(path, before, after)
