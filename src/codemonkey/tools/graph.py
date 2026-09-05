"""Graph-grounded retrieval tools (loop 28 → wired in loop 38, cycle 74).

Exposes `graphify-out/graph.json` to the agent itself:
  graph_query(symbol)  — pinned nodes + their edges (both ends)
  graph_path(a, b)     — BFS multi-hop relation path between two symbols
  graph_explain(name)  — the node + prose snippets that mention it

If graphify-out/ is absent the tools say so honestly (no fake results). If the
graph is older than HEAD (mtime of graph.json < the newest commit date), the
output carries an in-band `[stale: ...]` marker — a stale graph is worse than
none, so it is never silently trusted (AGENTS.md §graphify rule 2).

No-match contract (74F5, same rule for all three tools): a well-formed query
that matches nothing is a SUCCESSFUL result (ok=True) carrying an explicit
no-match line (`(no node matches '...')` / `no path: ...`). ok=False is
reserved for an unusable graph (none present) or bad arguments.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .base import ToolResult, _err
from .. import graphquery

# staleness: graph.json mtime vs last commit time (seconds of slack)
_STALE_SLACK_S = 5.0


def _check_staleness(graph_dir: Path, workdir: Path) -> str:
    """Return '' when fresh (or undeterminable), else a human marker."""
    try:
        import os

        if Path(graph_dir).is_file():  # single-file fallback layout (74F4)
            graph_files = [Path(graph_dir)]
        else:
            graph_files = [p for p in Path(graph_dir).rglob("*.json")]
        if not graph_files:
            return "[stale: no graph json found]"
        graph_mtime = max(os.path.getmtime(p) for p in graph_files)
        r = subprocess.run(
            ["git", "-C", str(workdir), "log", "-1", "--format=%ct"],
            capture_output=True, text=True, timeout=10,
        )
        commit_ts = float(r.stdout.strip())
    except Exception:
        return ""  # cannot determine -> do not claim staleness
    if graph_mtime < commit_ts - _STALE_SLACK_S:
        return ("[stale: graph is older than HEAD; refresh with "
                "`graphify . --update` before trusting structural answers]")
    return ""


def _fmt_node(n: dict) -> str:
    nid = n.get("id", "?")
    src = n.get("src", n.get("loc", ""))
    label = n.get("label", n.get("name", ""))
    return f"{nid}" + (f" [{label}]" if label and label != nid else "") + (
        f" ({src})" if src else "")


def _edges_text(edges: list, max_results: int) -> str:
    if not edges:
        return "(no edges recorded)"
    out = []
    for e in edges[:max_results]:
        out.append(f"- {e.get('source','?')} -> {e.get('target','?')}"
                   + (f" [{e.get('relation', e.get('type', ''))}]"
                      if e.get("relation") or e.get("type") else ""))
    return "\n".join(out)


def run(args: dict, ctx) -> "object":
    try:
        from .base import ToolResult

        symbol = str(args.get("symbol", "")).strip()
        if not symbol:
            return ToolResult(output="error: graph_query needs 'symbol'", ok=False)
        from ..sandbox import validate_root

        workdir = validate_root(ctx, ".")
        gdir = graphquery.find_graph_dir(workdir)
        if gdir is None:
            return ToolResult(
                output="error: no graphify-out/ graph in this workspace "
                       "(build one with `graphify .`); refusing to guess "
                       "structure without it",
                ok=False,
            )
        stale = _check_staleness(gdir, workdir)
        graph = graphquery.load_graph(gdir)
        res = graphquery.graph_query(graph, symbol,
                                     max_results=int(args.get("max_results", 20) or 20))
        lines = []
        if stale:
            lines.append(stale)
        if not res["matches"]:
            # 74F5 no-match contract: a well-formed query matching nothing is
            # ok=True with an explicit no-match line — only an unusable graph
            # or bad arguments is ok=False.
            lines.append(f"(no node matches '{symbol}')")
            return ToolResult(output="\n".join(lines),
                              meta={"stale": bool(stale), "matches": 0})
        else:
            lines.append(f"matches for '{symbol}':")
            for nid, n in list(res["matches"].items())[:10]:
                lines.append("  " + _fmt_node(n))
            edges_txt = _edges_text(res["edges"], int(args.get("max_results", 20) or 20))
            lines.append("edges:")
            lines.append(edges_txt)
        return ToolResult(output="\n".join(lines), meta={"stale": bool(stale)})
    except Exception as e:
        return _err(e)


def graph_path_lookup(workdir, a: str, b: str, *, max_depth: int = 4) -> dict:
    """Shortest relation path a -> b over graph edges (BFS). Staleness-aware.

    Result kinds (74F5 contract): "ok" = a real path; "no_path" = a
    well-formed query matching nothing (endpoints known or not, but no
    connectable path — a successful, explicit no-match answer); "error" =
    unusable graph or bad arguments.
    """
    if not a or not b:
        return {"kind": "error", "error": "both endpoints are required",
                "stale": "", "ok": False}
    gdir = graphquery.find_graph_dir(workdir)
    if gdir is None:
        return {"kind": "error", "ok": False,
                "error": "no graphify-out/ graph in this workspace",
                "stale": ""}
    stale = _check_staleness(gdir, Path(workdir))
    graph = graphquery.load_graph(gdir)
    edges = graph["edges"]

    def resolve(sym: str):
        """98F2: prefer an EXACT id/name match over a substring one.

        `graph_query`'s `max_results` caps edges, not matches, so
        `next(iter(matches))` returned whichever substring hit came first in
        node order — for `run_turns` that is
        `tests_test_knobs_test_exec_passes_knobs_to_run_turns`, so a
        one-hop path (`run_turns -> estimate_tokens`) reported "no path".
        """
        res = graphquery.graph_query(graph, sym)
        matches = res["matches"]
        if not matches:
            return None
        low = sym.lower()
        for nid, node in matches.items():
            name = str(node.get("name") or node.get("label") or "")
            if name.endswith("()"):
                name = name[:-2]
            if nid.lower() == low or name.lower() == low:
                return nid
        # no exact hit: shortest id wins over an arbitrary one (the least
        # decorated node bearing the name), still deterministic.
        return min(matches, key=lambda n: (len(n), n))

    sa, sb = resolve(a), resolve(b)
    if sa is None or sb is None:
        # 74F5: unresolved endpoints on a usable graph = a successful
        # no-match answer (ok=True, kind=no_path), not an error.
        missing = [name for name, val in ((a, sa), (b, sb)) if val is None]
        return {"kind": "no_path", "ok": True,
                "error": "no path: unresolved endpoint(s) " + ", ".join(repr(m) for m in missing),
                "stale": stale}
    # BFS over adjacency
    from collections import deque

    adj: dict = {}
    for e in edges:
        adj.setdefault(e.get("source"), []).append(e.get("target"))
    prev = {sa: None}
    q = [sa]
    depth = {sa: 0}
    while q:
        cur = q.pop(0)
        if depth[cur] >= max_depth:
            continue
        for nxt in adj.get(cur, []):
            if nxt not in prev:
                prev[nxt] = cur
                depth[nxt] = depth[cur] + 1
                q.append(nxt)
                if nxt == sb:
                    q = []
                    break
    if sb not in prev:
        return {"kind": "no_path", "ok": True,
                "error": f"no path: {a!r} -> {b!r} within {max_depth} hops",
                "stale": stale}
    path = []
    n = sb
    while n is not None:
        path.append(n)
        n = prev[n]
    path.reverse()
    return {"kind": "ok", "ok": True, "path": path, "stale": stale}


def run_path(args: dict, ctx) -> "object":
    try:
        from .base import ToolResult

        a = str(args.get("from", args.get("a", ""))).strip()
        b = str(args.get("to", args.get("b", ""))).strip()
        if not a or not b:
            return ToolResult(output="error: graph_path needs 'from' and 'to'",
                              ok=False)
        from ..sandbox import validate_root

        workdir = validate_root(ctx, ".")
        res = graph_path_lookup(workdir, a, b,
                                max_depth=int(args.get("max_depth", 4) or 4))
        lines = []
        if res.get("stale"):
            lines.append(res["stale"])
        if res["kind"] != "ok":
            # no_path = successful no-match (74F5); error = unusable graph/args
            lines.append(f"error: {res['error']}" if res["kind"] == "error"
                         else res["error"])
            return ToolResult(output="\n".join(lines),
                              ok=(res["kind"] != "error"),
                              meta={"stale": bool(res.get("stale")),
                                    "kind": res["kind"]})
        lines.append("path: " + " -> ".join(res["path"]))
        return ToolResult(output="\n".join(lines), meta={"stale": bool(res.get("stale")),
                                                         "kind": "ok"})
    except Exception as e:
        return _err(e)


def _explain_local(workdir, name: str) -> dict:
    gdir = graphquery.find_graph_dir(workdir)
    if gdir is None:
        return {"kind": "error", "ok": False, "error": "no graphify-out/ graph in this workspace",
                "text": ""}
    stale = _check_staleness(gdir, Path(workdir))
    graph = graphquery.load_graph(gdir)
    res = graphquery.graph_query(graph, name, max_results=20)
    lines = []
    if stale:
        lines.append(stale)
    if not res["matches"]:
        # 74F5: well-formed query matching nothing = ok=True, explicit line
        lines.append(f"(no node matches '{name}')")
    else:
        for nid, n in list(res["matches"].items())[:5]:
            lines.append(_fmt_node(n))
            if n.get("summary"):
                lines.append("  " + str(n["summary"])[:400])
            elif n.get("doc"):
                lines.append("  " + str(n["doc"])[:400])
        edges_txt = _edges_text(res["edges"], 20)
        lines.append("edges:")
        lines.append(edges_txt)
    matched = bool(res["matches"])
    return {"kind": ("ok" if matched else "no_match"), "ok": True,
            "text": "\n".join(lines),
            "stale": stale}


def run_explain(args: dict, ctx) -> "object":
    try:
        from .base import ToolResult

        name = str(args.get("name", args.get("symbol", ""))).strip()
        if not name:
            return ToolResult(output="error: graph_explain needs 'name'", ok=False)
        from ..sandbox import validate_root

        workdir = validate_root(ctx, ".")
        res = _explain_local(workdir, name)
        return ToolResult(output=res["text"] or res.get("error", ""),
                          ok=res["ok"],
                          meta={"stale": bool(res.get("stale")),
                                "kind": res["kind"]})
    except Exception as e:
        return _err(e)


# One module, three tool entry points: the registry maps each name to a shim
# exposing the right `run` (dispatch calls `<entry>.run(args, ctx)`).
class GraphQueryTool:
    run = staticmethod(run)


class GraphPathTool:
    run = staticmethod(run_path)


class GraphExplainTool:
    run = staticmethod(run_explain)
