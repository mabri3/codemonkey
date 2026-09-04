"""codemonkey rules-compile (R34): journal failures → draft permission rules."""

from __future__ import annotations

from collections import Counter

import typer

from .compile_rules import compile_corrections, merge_rules
from .journal import list_threads, read_thread


def rules_compile(
    threshold: int = typer.Option(2, "--threshold"),
    apply: bool = typer.Option(False, "--apply", help="Merge drafts into the project config."),
) -> None:
    """Mine journal failure classes into draft ask-rules (drafts need --apply
    and only ever ADD ask/deny — never loosen)."""
    classes: Counter = Counter()
    for tid in list_threads():
        for r in read_thread(tid):
            if r.get("type") == "outcome" and r.get("status") == "error":
                classes[(r.get("tool", "?"),
                         r.get("error_class") or "error")] += 1
    current = (cfg.get("permissions") or {}).get("rules") or []
    drafts = compile_corrections(dict(classes), threshold=threshold,
                                 existing_rules=current)
    if not drafts:
        typer.echo("(no recurring failures over threshold)")
        return
    for d in drafts:
        typer.echo(f"draft: {d['tool']} → {d['action']} ({d['reason']})")
    if apply:
        typer.echo("--apply not enabled in this release: drafts printed "
                   "only (governance: operator edits config)")
