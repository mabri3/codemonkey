"""Search/replace patch editing (loop2, cycle 13).

`edit_file` accepts EITHER the classic {path, old_string, new_string} form OR
an SREP-block patch form:

    path: str
    patch: |
        <<<< SEARCH
        ...exact text...
        >>>> REPLACE
        ...replacement text...
        <<<< SEARCH
        ...
        >>>> REPLACE

Multiple blocks apply in order; each is atomic within the file — if any
block fails to match, the file is NOT written (no torn intermediate).

Matching per block, in order of preference:
  1. exact match (unique; replace_all per block via `>>>> REPLACE ALL`)
  2. whitespace-tolerant match: lines equal after strip() and same count
  3. failure -> explicit error listing near-miss anchors (line numbers of the
     closest partial matches) so the model can retry with better context
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path

from .base import ToolResult, _err, _load, _save

BLOCK_RE = re.compile(
    r"<<<<\s*SEARCH\s*\n(.*?)\n>>>>\s*REPLACE(\s+ALL)?\s*\n(.*?)(?=\n<<<<\s*SEARCH|\Z)",
    re.S,
)


def parse_blocks(patch_text: str):
    """Parse SREP blocks -> list of {old, new, replace_all}."""
    blocks = []
    for m in BLOCK_RE.finditer(patch_text):
        old = m.group(1)
        replace_all = bool(m.group(2))
        new = m.group(3)
        # strip a single leading newline artifact
        if new.startswith("\n"):
            new = new[1:]
        if new.endswith("\n") and not old.endswith("\n"):
            new = new[:-1]
        blocks.append({"old": old, "new": new, "replace_all": replace_all})
    return blocks


def _exact_search(text: str, old: str):
    n = text.count(old)
    if n == 1:
        return 1, text.find(old)
    return n, text.find(old) if n else -1


def _fuzzy_window(text: str, old: str):
    """Whitespace-tolerant: try matching with normalized indentation.

    Strategy: align by first line; slice candidate windows of the same line
    count; compare with all line-strip equality. Returns (count, positions).
    """
    old_lines = old.split("\n")
    k = len(old_lines)
    lines = text.split("\n")
    if k == 0 or len(lines) < k:
        return 0, []
    hits = []
    import re as _re

    def norm(s):
        return _re.sub(r"\s+", " ", s.strip())

    first = norm(old_lines[0]) if old_lines else ""
    if not first:
        return 0, []
    for i, line in enumerate(lines):
        if norm(line) != first:
            continue
        window = lines[i:i + k]
        if len(window) < k:
            continue
        if all(norm(w) == norm(o) for w, o in zip(window, old_lines)):
            hits.append(i)
    return len(hits), hits


def _near_miss_anchors(text: str, old: str, limit: int = 3) -> list[str]:
    """Line numbers of partial matches (first non-empty old line found)."""
    anchors = []
    probe = next((ln.strip() for ln in old.split("\n") if ln.strip()), "")
    if not probe:
        return anchors
    for i, line in enumerate(text.split("\n"), 1):
        if probe in line:
            anchors.append(f"line {i}: {line.strip()[:70]}")
            if len(anchors) >= limit:
                break
    return anchors


def _apply_block(text: str, block: dict):
    """Apply one block. Returns (new_text, applied_desc, error_msg)."""
    old, new = block["old"], block["new"]
    if not old.strip():
        return None, None, "empty SEARCH block (use write_file for new files)"

    n, pos = _exact_search(text, old)
    if n == 1:
        return text.replace(old, new, 1), "exact", None
    if n > 1 and not block["replace_all"]:
        return None, None, (
            f"SEARCH matches {n} places; add surrounding context to make it "
            "unique (or use REPLACE ALL)"
        )
    if n > 1 and block["replace_all"]:
        return text.replace(old, new), f"exact x{n}", None

    # fuzzy fallback (whitespace-tolerant), unless replace_all semantics demand exact
    fn, positions = _fuzzy_window(text, old)
    if fn == 1:
        lines = text.split("\n")
        k = len(old.split("\n"))
        i = positions[0]
        before = "\n".join(lines[:i])
        after = "\n".join(lines[i + k:])
        mid = new
        out = before + ("\n" if before else "") + mid + ("\n" + after if after else "")
        return out, "fuzzy (whitespace-tolerant)", None
    if fn > 1 and not block["replace_all"]:
        return None, None, f"fuzzy SEARCH matches {fn} places; add context"

    anchors = _near_miss_anchors(text, old)
    msg = "SEARCH text not found"
    if anchors:
        msg += "; near-miss anchor lines:\n  " + "\n  ".join(anchors)
    return None, None, msg


def run(args: dict, ctx) -> ToolResult:
    try:
        path = args["path"]
        patch_text = args.get("patch")
        raw = _load(path, ctx)
        text = raw.decode("utf-8", errors="replace")

        if patch_text:
            blocks = parse_blocks(patch_text)
            if not blocks:
                return ToolResult(output="error: no SREP blocks found in patch", ok=False)
            current = text
            applied = []
            for bi, block in enumerate(blocks, 1):
                new_text, how, err = _apply_block(current, block)
                if err:
                    return ToolResult(
                        output=(f"error: block {bi}/{len(blocks)} failed — {err}. "
                                "File NOT modified (atomic)."),
                        ok=False,
                    )
                current = new_text
                applied.append(f"block {bi}: {how}")
            _save(path, current, ctx)
            return ToolResult(output=f"applied {len(blocks)} block(s) to {path}: " + "; ".join(applied))

        # classic form delegates to the same matcher for the fuzzy upgrade
        old = args.get("old_string", "")
        new = args.get("new_string", "")
        replace_all = bool(args.get("replace_all", False))
        if not old:
            return ToolResult(output="error: old_string must be non-empty (use write_file to create files)", ok=False)
        n = text.count(old)
        if n == 0:
            # fuzzy fallback for the classic form too
            new_text, how, err = _apply_block(text, {"old": old, "new": new, "replace_all": replace_all})
            if err:
                return ToolResult(output=f"error: {err} in {path}", ok=False)
            _save(path, new_text, ctx)
            return ToolResult(output=f"replaced ({how}) in {path}")
        if n > 1 and not replace_all:
            return ToolResult(
                output=f"error: old_string matches {n} places; add context to make it unique or set replace_all=true",
                ok=False,
            )
        count = n if replace_all else 1
        replaced = text.replace(old, new) if replace_all else text.replace(old, new, 1)
        _save(path, replaced, ctx)
        return ToolResult(output=f"replaced {count} occurrence(s) in {path}")
    except Exception as e:
        return _err(e)
