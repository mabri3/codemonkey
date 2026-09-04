"""Tool registry: name -> (run, spec) for prompt-protocol advertising + dispatch."""

from __future__ import annotations
from . import (
    edit_file,
    glob,
    list_dir,
    read_file,
    search,
    shell,
    delegate,
    delegate_batch,
    repo_map,
    update_memory,
    update_plan,
    web_fetch,
    write_file,
    graph as graph_mod,
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
    "delegate": delegate,
    "delegate_batch": delegate_batch,
    "repo_map": repo_map,
    "update_memory": update_memory,
    "update_plan": update_plan,
    "web_fetch": web_fetch,
    "graph_query": graph_mod.GraphQueryTool,
    "graph_path": graph_mod.GraphPathTool,
    "graph_explain": graph_mod.GraphExplainTool,
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
    "delegate": "delegate(task='...', sandbox='workspace-write') -> run an isolated child codemonkey run and return its final result",
    "delegate_batch": "delegate_batch(tasks=[...]) -> run multiple isolated child runs (max_delegates workers), results in call order",
    "repo_map": "repo_map(path='.', pattern=None, limit=200) -> symbol index (file, kind, line) of the repo",
    "update_memory": "update_memory(fact) -> append a durable fact to memory (disabled when strategies.memory=none)",
    "update_plan": "update_plan(mode=append|replace|clear, content, id, status=pending|in_progress|completed) -> renders plan",
    "web_fetch": "web_fetch(url) -> bounded GET (60s, 512KB) of a doc page",
    "graph_query": "graph_query(symbol, max_results=20) -> graphify nodes matching symbol + their edges (reports [stale] when the graph is older than HEAD)",
    "graph_path": "graph_path(from, to, max_depth=4) -> shortest relation path between two symbols in the code graph",
    "graph_explain": "graph_explain(name) -> node summary + neighbors for a codebase symbol from the code graph",
}


# JSON Schema for each tool's arguments, fed to the provider-native tool
# protocols (OpenAI `parameters` / Anthropic `input_schema`).
#
# 51F1: these used to be omitted entirely — native.openai_tool_specs sent
# `{"type": "object", "properties": {}}` for every tool, so the wire schema
# told the model the tools took NO arguments. Models that follow the declared
# schema (rather than guessing from the SPECS prose) correctly answered with
# `{}`, and every call died on a KeyError — e.g. shell's args["command"]
# surfacing as `error: 'command'`. The one-line SPECS strings stay as the
# human-readable descriptions; the machine-readable contract lives here.
def _s(desc: str) -> dict:
    return {"type": "string", "description": desc}


def _i(desc: str, default: int) -> dict:
    return {"type": "integer", "description": f"{desc} (default {default})"}


PARAMS: dict[str, dict] = {
    "read_file": {
        "type": "object",
        "properties": {
            "path": _s("File to read, relative to the workspace root."),
            "offset": _i("1-based first line to read.", 1),
            "limit": _i("Maximum number of lines to return.", 2000),
        },
        "required": ["path"],
    },
    "write_file": {
        "type": "object",
        "properties": {
            "path": _s("File to write, relative to the workspace root."),
            "content": _s("Full new contents; overwrites the whole file."),
        },
        "required": ["path", "content"],
    },
    "edit_file": {
        "type": "object",
        "properties": {
            "path": _s("File to edit (single-edit form)."),
            "old_string": _s("Exact text to replace; must match uniquely."),
            "new_string": _s("Replacement text."),
            "replace_all": {
                "type": "boolean",
                "description": "Replace every occurrence instead of requiring a unique match.",
            },
            "patch": _s("SREP search/replace block, as an alternative to old_string/new_string."),
            "edits": {
                "type": "array",
                "description": "Batched multi-file edits, applied atomically (all-or-nothing).",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": _s("File to edit."),
                        "patch": _s("SREP block for this file."),
                        "search": _s("Exact text to find."),
                        "replace": _s("Replacement text."),
                    },
                    "required": ["path"],
                },
            },
        },
    },
    "list_dir": {
        "type": "object",
        "properties": {"path": _s("Directory to list (default '.').")},
    },
    "glob": {
        "type": "object",
        "properties": {
            "pattern": _s("Glob pattern, e.g. '**/*.py'."),
            "path": _s("Directory to search from (default '.')."),
            "limit": _i("Maximum paths to return.", 100),
        },
        "required": ["pattern"],
    },
    "search": {
        "type": "object",
        "properties": {
            "pattern": _s("Regular expression to search for."),
            "path": _s("Directory to search from (default '.')."),
            "file_glob": _s("Restrict matches to files matching this glob."),
            "limit": _i("Maximum matches to return.", 50),
        },
        "required": ["pattern"],
    },
    "shell": {
        "type": "object",
        "properties": {
            "command": _s("Shell command to run via `bash -lc` in the workspace."),
        },
        "required": ["command"],
    },
    "delegate": {
        "type": "object",
        "properties": {
            "task": _s("Task for the isolated child run."),
            "role": _s("Child role, e.g. 'implementer' or 'reviewer'."),
            "review_rounds": _i("Adversarial review rounds to run.", 0),
            "sandbox": _s("Sandbox policy for the child run."),
        },
        "required": ["task"],
    },
    "delegate_batch": {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "description": "Tasks to run as isolated child runs; results come back in call order.",
                "items": {"type": "string"},
            },
        },
        "required": ["tasks"],
    },
    "repo_map": {
        "type": "object",
        "properties": {
            "path": _s("Directory to scan (default '.')."),
            "pattern": _s("Only report symbols matching this pattern."),
            "limit": _i("Maximum symbols to return.", 200),
        },
    },
    "update_memory": {
        "type": "object",
        "properties": {"fact": _s("Durable fact to append to memory.")},
        "required": ["fact"],
    },
    "update_plan": {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["append", "replace", "clear"],
                "description": "How to apply this update (default 'append').",
            },
            "content": _s("Plan item text."),
            "id": _s("Plan item id; defaults to the next free id."),
            "status": {
                "type": "string",
                "enum": ["pending", "in_progress", "completed"],
                "description": "Item status (default 'pending').",
            },
        },
    },
    "web_fetch": {
        "type": "object",
        "properties": {"url": _s("URL to GET (bounded: 60s, 512KB).")},
        "required": ["url"],
    },
    "graph_query": {
        "type": "object",
        "properties": {
            "symbol": _s("Symbol, file or concept name to look up in the code graph."),
            "max_results": _i("Maximum edges to return.", 20),
        },
        "required": ["symbol"],
    },
    "graph_path": {
        "type": "object",
        "properties": {
            "from": _s("Start symbol."),
            "to": _s("End symbol."),
            "max_depth": _i("Maximum path hops.", 4),
        },
        "required": ["from", "to"],
    },
    "graph_explain": {
        "type": "object",
        "properties": {"name": _s("Symbol/concept to explain from the code graph.")},
        "required": ["name"],
    },
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
    # 14F1: every file snapshotted by this call joins ONE checkpoint group, so
    # `codemonkey undo` reverses a multi-file edit whole instead of in part.
    from .. import checkpoints as cp_mod

    cp_mod.begin_call()
    try:
        return mod.run(args, ctx)
    finally:
        cp_mod.end_call()


__all__ = ["names", "dispatch", "SPECS", "PARAMS", "_MODULES"]
