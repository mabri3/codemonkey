"""Repo map: dependency-free symbol scan (loop4, cycle 20).

Scans source files for top-level definitions (def/class/func/const/struct...)
across py/js/ts/go/rs/java/rb, producing file -> [{symbol, kind, line}] with
1-BASED line numbers. No tree-sitter — regex-graded scan (~80% of the value,
zero deps; loop-3 research noted full AST indexing as a later upgrade).

Cache: .codemonkey/repomap.json keyed by relpath with (mtime, size); unchanged
files are not re-scanned. Ignore list: .git, .venv, node_modules,
__pycache__, .codemonkey, dist, build artifacts.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

IGNORE_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__",
               ".codemonkey", "dist", "build", ".pytest_cache", ".mypy_cache"}
SCANNABLE = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".rb"}

# language -> list of (regex, kind)
PATTERNS = {
    ".py": [
        (re.compile(r"^(\s*)def\s+([A-Za-z_]\w*)"), "def"),
        (re.compile(r"^(\s*)class\s+([A-Za-z_]\w*)"), "class"),
    ],
    ".js": [
        (re.compile(r"^\s*function\s+([A-Za-z_$][\w$]*)"), "function"),
        (re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\("), "function"),
        (re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_$][\w$]*)"), "class"),
    ],
    ".ts": None,  # filled below from .js
    ".tsx": None,
    ".jsx": None,
    ".go": [
        (re.compile(r"^func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)"), "func"),
        (re.compile(r"^type\s+([A-Za-z_]\w*)\s+struct"), "struct"),
    ],
    ".rs": [
        (re.compile(r"^\s*(?:pub\s+)?fn\s+([A-Za-z_]\w*)"), "fn"),
        (re.compile(r"^\s*(?:pub\s+)?struct\s+([A-Za-z_]\w*)"), "struct"),
    ],
    ".java": [
        (re.compile(r"^\s*(?:public|private|protected)?\s*(?:static\s+)?class\s+([A-Za-z_]\w*)"), "class"),
        (re.compile(r"^\s*(?:public|private|protected)\s+\w[\w<>\[\],\s]*\s+([A-Za-z_]\w*)\s*\("), "method"),
    ],
    ".rb": [
        (re.compile(r"^\s*def\s+([A-Za-z_]\w*[?!]?)"), "def"),
        (re.compile(r"^\s*class\s+([A-Za-z_]\w*)"), "class"),
    ],
}
PATTERNS[".ts"] = PATTERNS[".js"]
PATTERNS[".tsx"] = PATTERNS[".js"]
PATTERNS[".jsx"] = PATTERNS[".js"]


def cache_path(workdir: Path) -> Path:
    return Path(workdir) / ".codemonkey" / "repomap.json"


def _load_cache(workdir: Path) -> dict:
    p = cache_path(workdir)
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(workdir: Path, cache: dict) -> None:
    p = cache_path(workdir)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(cache))
    except OSError:
        pass


def scan_file(path: Path):
    """Scan one file -> list of {symbol, kind, line} (1-based) or None on skip."""
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError):
        return None
    pats = PATTERNS.get(path.suffix)
    if not pats:
        return None
    out = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for rx, kind in pats:
            m = rx.match(line)
            if m:
                sym = m.group(2) if rx.groups >= 2 else m.group(1)
                out.append({"symbol": sym, "kind": kind, "line": lineno})
                break
    return out


def scan_repo(workdir: Path, *, use_cache: bool = True,
              cache_hits: list | None = None) -> dict:
    """Scan the repo tree -> {relpath: [entries]}. Uses mtime+size cache."""
    workdir = Path(workdir).resolve()
    cache = _load_cache(workdir) if use_cache else {}
    new_cache = {}
    result = {}
    for p in sorted(workdir.rglob("*")):
        if not p.is_file() or p.suffix not in SCANNABLE:
            continue
        rel = p.relative_to(workdir).as_posix()
        if any(part in IGNORE_DIRS for part in p.relative_to(workdir).parts[:-1]):
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        key = f"{rel}"
        entry = cache.get(key)
        if use_cache and entry and entry.get("mtime") == st.st_mtime and entry.get("size") == st.st_size:
            result[rel] = entry["symbols"]
            new_cache[key] = entry
            if cache_hits is not None:
                cache_hits.append(rel)
            continue
        syms = scan_file(p)
        if syms:
            result[rel] = syms
            new_cache[key] = {"mtime": st.st_mtime, "size": st.st_size, "symbols": syms}
    if use_cache:
        _save_cache(workdir, new_cache)
    return result


def format_map(repo_map: dict, *, pattern: str | None = None,
               limit: int = 200) -> str:
    """Deterministic text rendering: files sorted, entries in line order."""
    import fnmatch

    lines = []
    count = 0
    for rel in sorted(repo_map):
        if pattern and not fnmatch.fnmatch(rel, pattern):
            continue
        entries = sorted(repo_map[rel], key=lambda e: e["line"])
        lines.append(f"{rel}:")
        for e in entries:
            if limit and count >= limit:
                lines.append(f"  ...[truncated at {limit} entries]")
                return "\n".join(lines)
            lines.append(f"  L{e['line']:>5}  {e['kind']:>8}  {e['symbol']}")
            count += 1
    return "\n".join(lines) if lines else "(no symbols found)"
