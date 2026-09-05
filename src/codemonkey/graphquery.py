"""Graph-grounded retrieval (R28).

The repo ships graphify-out/ for human agents; expose it as a `graph_query`
tool: pinned-symbol lookup, import/relation neighbors, borderline grep+
graph merge. If graphify-out/ is absent the tool says so honestly (no fake
results).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


def find_graph_dir(workdir) -> Optional[Path]:
    """Locate graphify-out/ (or graph.json fallback) relative to workdir."""
    for candidate in (Path(workdir) / "graphify-out",
                      Path(workdir) / ".graphify"):
        if candidate.is_dir() and any(candidate.glob("*.json")):
            return candidate
    single = Path(workdir) / "graph.json"
    if single.is_file():
        return single
    return None


# 98F1: graphify writes relationships under "links" (node-link JSON); the
# per-file AST cache fragments use "edges". Reading only one key silently
# drops the other side of the graph — see the module note below.
_EDGE_KEYS = ("links", "edges")


def load_graph(graph_dir: Path) -> dict:
    """Merge the CURRENT graph's JSON artifacts into {nodes, edges}.

    Accepts both layouts `find_graph_dir` can return: a directory or the
    single-file fallback (graph.json itself). 74F4: the file layout must be
    LOADABLE, not silently answered from an empty graph.

    98F1 — two defects fixed here, both silent:

    1. **Wrong key.** This read only `data["edges"]`, but `graphify-out/
       graph.json` stores relationships under `"links"`. Only the per-file
       AST cache fragments carry an `"edges"` key, so 100% of the edges
       every consumer saw came from single-file extractions — same-file by
       construction. That is the entire reason C98 measured "zero
       cross-file calls" in a graph holding 892 of them.
    2. **Wrong scope.** `rglob` swept `cache/ast/` fragments and the dated
       backup snapshots, so the merged graph served nodes from modules
       deleted in cycle 81 (`rolepresets`, `lessons_gate`, `truthpass`) as
       if they were live — the exact thing R-L forbids of a research file.

    Scope is now the graph directory's own `*.json` (non-recursive): the
    current graph, never its backups or its cache.
    """
    nodes: dict = {}
    edges: list = []
    paths = ([graph_dir] if graph_dir.is_file()
             else sorted(graph_dir.glob("*.json")))
    for p in paths:
        try:
            data = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        for n in data.get("nodes", []) or []:
            if isinstance(n, dict) and n.get("id"):
                nodes[n["id"]] = n
        for key in _EDGE_KEYS:
            edges.extend(data.get(key, []) or [])
    return {"nodes": nodes, "edges": edges}


def graph_query(graph: dict, symbol: str, *, max_results: int = 20) -> dict:
    """Pinned nodes whose id/name matches, plus their edges (both ends)."""
    sym = symbol.lower()
    hits = {nid: n for nid, n in graph["nodes"].items()
            if sym == nid.lower()
            or sym == str(n.get("name", "")).lower()
            or sym in nid.lower()}

    hit_ids = set(hits)
    related = [e for e in graph["edges"]
               if e.get("source") in hit_ids or e.get("target") in hit_ids]
    return {"matches": hits, "edges": related[:max_results]}
