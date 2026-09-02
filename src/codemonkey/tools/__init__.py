"""Tool registry: name -> (run, spec) for prompt-protocol advertising + dispatch."""

from __future__ import annotations
from . import (
    edit_file,
    glob,
    list_dir,
    read_file,
    search,
    shell,
    update_plan,
    web_fetch,
    write_file,
)

# name -> module; every module exposes run(args, ctx) -> ToolResult
_MODULES = {
    "read_file": read_file,
    "write_file": write_file,
    "edit_file": edit_file,
    "list_dir": list_dir,
    "glob": glob,
    "search": search,
    "shell": shell,
    "update_plan": update_plan,
    "web_fetch": web_fetch,
}

# human-readable one-line specs for the prompt-protocol system block
SPECS = {
    "read_file": "read_file(path, offset=1, limit=2000) -> numbered lines with [total_lines=N]",
    "write_file": "write_file(path, content) -> overwrites the whole file",
    "edit_file": "edit_file(path, old_string, new_string, replace_all=false) -> unique-match replacement; rejects ambiguous",
    "list_dir": "list_dir(path='.') -> dir/file entries with sizes, mtime-desc",
    "glob": "glob(pattern, path='.', limit=100) -> matching file paths, newest first",
    "search": "search(pattern, path='.', file_glob, limit=50) -> file:line: text matches (rg-backed)",
    "shell": "shell(command) -> bash -lc in workdir, timeout ctx.timeout (sandbox-gated)",
    "update_plan": "update_plan(mode=append|replace|clear, content, id, status=pending|in_progress|completed) -> renders plan",
    "web_fetch": "web_fetch(url) -> bounded GET (60s, 512KB) of a doc page",
}


def names() -> list[str]:
    return list(_MODULES)


def dispatch(name: str, args: dict, ctx):
    """Execute a tool by name; unknown names / sandbox violations -> ok=False result.

    The coarse sandbox gate runs here (before the tool) so every tool —
    including new ones — is policy-checked. Path-escape violations raise
    SandboxError from inside the tool and are caught there (ok=False).
    """
    from .base import ToolResult
    from ..sandbox import SandboxError, check

    mod = _MODULES.get(name)
    if mod is None:
        return ToolResult(output=f"error: unknown tool '{name}'", ok=False)
    try:
        check(name, ctx)
    except SandboxError as e:
        return ToolResult(output=f"sandbox-denied: {e}", ok=False)
    return mod.run(args, ctx)


__all__ = ["names", "dispatch", "SPECS", "_MODULES"]
