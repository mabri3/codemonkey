"""Pre-apply validation + symbol index (R29).

Two primitives, both client-side (no LSP server dependency):
1. pre_apply_validate(path, content) — python syntax check via ast.parse;
   JSON/YAML parse checks for data files. Returns error string or None.
   The write/edit tools call this before committing when strict is enabled.
2. symbol_index(workdir) — regex-based def index (def/class X at column 0)
   mapping symbol → [file:line]; replaces textual grep for symbol questions
   (grounding without an LSP server).
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Optional

_DEF_RE = re.compile(r"^(?:def|class)\s+([A-Za-z_]\w*)", re.M)


def pre_apply_validate(path: str, content: str) -> Optional[str]:
    """Syntax-level validation; returns error text or None."""
    p = str(path).lower()
    try:
        if p.endswith(".py"):
            ast.parse(content)
        elif p.endswith(".json"):
            json.loads(content)
    except SyntaxError as exc:
        return f"syntax error: {exc.msg} (line {exc.lineno})"
    except (json.JSONDecodeError, ValueError) as exc:
        return f"invalid JSON: {exc}"
    return None


def symbol_index(workdir, *, max_files: int = 2000) -> dict[str, list[str]]:
    """{symbol: [relative_path:lineno, ...]} for python files."""
    root = Path(workdir)
    index: dict[str, list[str]] = {}
    count = 0
    for py in sorted(root.rglob("*.py")):
        if count >= max_files or ".venv" in py.parts or "node_modules" in py.parts:
            continue
        count += 1
        try:
            text = py.read_text(errors="replace")
        except OSError:
            continue
        rel = py.relative_to(root)
        for m in _DEF_RE.finditer(text):
            line = text[:m.start()].count("\n") + 1
            index.setdefault(m.group(1), []).append(f"{rel}:{line}")
    return index


def locate(index: dict[str, list[str]], symbol: str) -> list[str]:
    """Definition sites (exact first, then prefix matches, capped)."""
    if symbol in index:
        return index[symbol][:10]
    sym = symbol.lower()
    hits: list[str] = []
    for name, sites in index.items():
        if name.lower().startswith(sym):
            hits.extend(sites)
        if len(hits) >= 10:
            break
    return hits[:10]
