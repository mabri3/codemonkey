"""search — grep over files; prefers `rg` on PATH, falls back to a pure-Python walk."""

from __future__ import annotations
import re
import shutil
import subprocess
from pathlib import Path
from .base import ToolResult, _err
from ..sandbox import validate_root


def _python_search(root: Path, pattern: str, file_glob: str, max_hits: int):
    rx = re.compile(pattern)
    hits = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if file_glob and not p.name.match(file_glob):
            continue
        try:
            text = p.read_text(errors="ignore")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                hits.append(f"{p}:{i}: {line[:300]}")
                if len(hits) >= max_hits:
                    return hits
    return hits


def run(args: dict, ctx) -> ToolResult:
    try:
        root = validate_root(ctx, args.get("path", "."))
        pattern = args["pattern"]
        limit = int(args.get("limit", 50))
        if shutil.which("rg"):
            cmd = ["rg", "-n", "--no-heading", pattern, str(root)]
            fg = args.get("file_glob")
            if fg:
                cmd += ["-g", fg]
            cmd += ["-m", str(limit * 2)]
            p = subprocess.run(cmd, capture_output=True, text=True, cwd=ctx.workdir, timeout=60)
            if p.returncode not in (0, 1):
                return _err(RuntimeError(f"rg failed: {p.stderr.strip()}"))
            return ToolResult(output=p.stdout[:20000] or "(no matches)")
        hits = _python_search(root, pattern, args.get("file_glob"), limit)
        if not hits:
            return ToolResult(output="(no matches)")
        return ToolResult(output="\n".join(hits))
    except Exception as e:
        return _err(e)
