"""Change-impact analysis: graph-grounded vs search-driven (loop 41, C98).

R-L correction, measured 2026-09-05 (see research-loop41.md correction):
the loop-28 graph's AST extractor resolves module structure (contains /
imports / imports_from) and SAME-FILE calls only — all 1,119 resolvable
`calls` edges in this repo are same-file, zero cross-file. So this module
does NOT claim cross-file caller coverage from `calls` edges. What the
graph actually contributes over grep:

1. Importers with binding info: `imports_from` (a NAME is bound here —
   `from m import target [as t]`, the file must change with a signature
   change) vs `imports` (module-level; use may be dynamic — review, don't
   assume). A search-driven plan sees string occurrences and cannot tell
   a bound call from a comment.
2. Precision: zero noise — comments, docstrings and substring coincidences
   (`retarget`) never appear as importers.

`graph_callers` is kept for same-file call sites (exact edge evidence) and
for the day the extractor emits cross-file calls — its test pins the
current empty-cross-file result so that day reopens the question instead
of passing silently.
"""

from __future__ import annotations

from pathlib import Path

CALL_REL = "calls"
IMPORTER_RELS = ("imports_from", "imports")


def _load(workdir: Path) -> dict:
    from .graphquery import find_graph_dir, load_graph

    gdir = find_graph_dir(workdir)
    if gdir is None:
        raise LookupError(f"no graphify-out/ graph in {workdir} "
                          "(build one with `graphify .`)")
    return load_graph(gdir)


def _node_name(node: dict) -> str:
    name = str(node.get("name") or node.get("label") or "")
    return name[:-2] if name.endswith("()") else name


def graph_callers(workdir: Path, symbol: str) -> dict:
    """Same-file call sites of `symbol` (edge evidence). Returns
    {file: [line, ...]}. Cross-file callers: not emitted by the extractor
    (measured 2026-09-05) — absent here means unobservable, not nonexistent.
    """
    graph = _load(workdir)
    nodes = graph["nodes"]
    out: dict[str, list] = {}
    for e in graph["edges"]:
        if e.get("relation") != CALL_REL:
            continue
        target = nodes.get(e.get("target", ""), {})
        if _node_name(target) != symbol:
            continue
        loc = e.get("source_location", "")
        out.setdefault(e.get("source_file", ""), []).append(loc)
    return out


def graph_importers(workdir: Path, module: str) -> dict:
    """Files importing `module`: {file: {relations}}. `imports_from` binds
    a name (signature changes propagate); `imports` is module-level."""
    graph = _load(workdir)
    out: dict[str, set] = {}
    for e in graph["edges"]:
        if e.get("relation") not in IMPORTER_RELS:
            continue
        tgt = str(e.get("target", ""))
        if tgt != module and not tgt.endswith("." + module):
            continue
        out.setdefault(e.get("source_file", ""), set()).add(e["relation"])
    return {f: sorted(r) for f, r in out.items()}


def search_files(workdir: Path, symbol: str) -> set[str]:
    """Files containing `symbol` via the REAL search tool (entry point,
    not a reimplementation). Regex-escaped symbol, no glob filter."""
    import re

    from .sandbox import ToolContext
    from .tools import search as search_tool

    ctx = ToolContext(workdir=Path(workdir).resolve())
    res = search_tool.run({"pattern": re.escape(symbol), "path": "."}, ctx)
    if not res.ok or res.output.strip() == "(no matches)":
        return set()
    found = set()
    wd = str(Path(workdir).resolve())
    for line in res.output.splitlines():
        path = line.split(":", 1)[0].strip()
        if path.startswith(wd):
            path = path[len(wd):].lstrip("/\\")
        found.add(path)
    return found


def compare(workdir: Path, module: str, symbol: str) -> dict:
    """Graph importers + same-file callers vs search files, both counts."""
    importers = graph_importers(workdir, module)
    callers = graph_callers(workdir, symbol)
    searched = search_files(workdir, symbol)
    gfiles = set(importers) | set(callers)
    return {
        "module": module,
        "symbol": symbol,
        "graph_importers": importers,
        "graph_callers": callers,
        "graph_files": sorted(gfiles),
        "search_files": sorted(searched),
        "graph_only": sorted(gfiles - searched),
        "search_only": sorted(searched - gfiles),
        "n_graph": len(gfiles),
        "n_search": len(searched),
    }
