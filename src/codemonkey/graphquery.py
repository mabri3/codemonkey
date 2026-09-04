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


def load_graph(graph_dir: Path) -> dict:
    """Merge all JSON artifacts into {nodes: {id: node}, edges: [...]}."""
    nodes: dict = {}
    edges: list = []
    for p in sorted(graph_dir.rglob("*.json")):
        try:
            data = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        for n in data.get("nodes", []) or []:
            if isinstance(n, dict) and n.get("id"):
                nodes[n["id"]] = n
        edges.extend(data.get("edges", []) or [])
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
