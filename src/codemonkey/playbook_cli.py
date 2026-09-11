"""`codemonkey playbook` — the operator surface for the evolving playbook.

Cycle 107 ships `list` (honest empty without a store), `show`, `merge`
(deltas in, deterministic merge out, report printed), `admit` and `revoke`.
Cycle 108 adds `reflect` (journal → evidence-cited deltas).
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

app = typer.Typer(help="Evolving playbook: quarantined, delta-curated, revocable.")


@app.command("list")
def list_cmd() -> None:
    """List every playbook entry with status, kind, section and counter.

    Exit 0 on an empty or missing store (honest empty); a corrupt store is a
    loud error (exit 2), never a silent empty."""
    from . import playbook

    cwd = Path.cwd()
    try:
        rows = playbook.list_entries(cwd)
    except playbook.PlaybookError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from None
    if not rows:
        typer.echo(f"no playbook entries ({playbook.store_path(cwd)})")
        raise typer.Exit(0)
    for e in rows:
        typer.echo(f"{e['id']}\t{e['status']}\t{e['kind']}/{e['section']}\t"
                   f"x{e.get('counter', 1)}\t{e['text']}")
    raise typer.Exit(0)


@app.command("show")
def show_cmd(
    entry_id: str = typer.Argument(..., help="playbook entry id (pb-…)"),
) -> None:
    """Print one entry's full record — text, counters, provenance, history."""
    from . import playbook

    try:
        e = playbook.get_entry(Path.cwd(), entry_id)
    except playbook.PlaybookError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from None
    typer.echo(f"{e['id']}  [{e['status']}]  {e['kind']}/{e['section']}")
    typer.echo(f"  text:     {e['text']}")
    typer.echo(f"  counter:  {e.get('counter', 1)}  "
               f"(first_seen {e.get('first_seen', '?')}, "
               f"last_seen {e.get('last_seen', '?')})")
    prov = e.get("provenance", {})
    typer.echo(f"  provenance: run_id={prov.get('run_id', '?')} "
               f"session_id={prov.get('session_id') or '-'} "
               f"taint_free={prov.get('taint_free', '?')}"
               + (f" source={prov['source']}" if prov.get("source") else ""))
    for h in e.get("history", []):
        typer.echo(f"  {h['at']}  {h['from']} -> {h['to']}  ({h['reason']})")
    raise typer.Exit(0)


@app.command("merge")
def merge_cmd(
    deltas_file: str = typer.Argument(..., help="JSON file: {\"deltas\": [...]} or a bare list"),
) -> None:
    """Merge candidate deltas through the deterministic path.

    Refused deltas are reported with index + reason and apply nothing.
    New entries land `quarantined`; re-merges bump counters in place without
    rewriting text (byte-stable). Exit 0 = merged (even with refusals, which
    are printed); 2 = store or input unreadable."""
    from . import journal, playbook

    cwd = Path.cwd()
    try:
        raw = json.loads(Path(deltas_file).read_text())
    except (OSError, ValueError) as exc:
        typer.echo(f"error: cannot read {deltas_file}: {exc}", err=True)
        raise typer.Exit(2) from None
    deltas = raw.get("deltas") if isinstance(raw, dict) else raw
    if not isinstance(deltas, list):
        typer.echo("error: deltas file must be a list or {\"deltas\": [...]}",
                   err=True)
        raise typer.Exit(2)
    try:
        report = playbook.merge_deltas(cwd, deltas)
    except playbook.PlaybookError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from None
    try:
        journal.record(playbook.playbook_thread(cwd), "playbook.merged",
                       tool="playbook", key="*",
                       status=f"added:{report['added']} updated:{report['updated']} "
                              f"refused:{len(report['refused'])}")
    except Exception:
        pass
    typer.echo(f"merged: added={report['added']} updated={report['updated']} "
               f"refused={len(report['refused'])} total={report['total']}")
    for r in report["refused"]:
        typer.echo(f"  refused delta[{r['index']}]: {r['reason']}")
    raise typer.Exit(0)


@app.command("stats")
def stats_cmd() -> None:
    """Entry counts by status, total words, total counter — the numbers the
    boundedness claims read. Exit 0 on a missing store (honest zeros with a
    note that the store does not exist; numbers, never a green)."""
    from . import playbook

    cwd = Path.cwd()
    try:
        st = playbook.store_stats(cwd)
    except playbook.PlaybookError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from None
    exists = playbook.store_path(cwd).exists()
    note = "" if exists else " (store does not exist yet)"
    bs = st["by_status"]
    typer.echo(f"entries={st['entries']}{note}  words={st['words']}  "
               f"counter_total={st['counter_total']}")
    typer.echo(f"  quarantined={bs['quarantined']} admitted={bs['admitted']} "
               f"evicted={bs['evicted']}")
    raise typer.Exit(0)


@app.command("reflect")
def reflect_cmd(
    thread: str = typer.Argument(..., help="journal thread to reflect on"),
    out: str = typer.Option("", "--out", help="write deltas JSON to this file "
                                              "(default: stdout)"),
) -> None:
    """Reflect a thread's journal into candidate deltas (JSON).

    PURE: no model call, no merge — the store is untouched. Save the output
    and hand it to `playbook merge` explicitly (or pipe it). An empty or
    missing thread reflects to `[]` (honest empty, exit 0)."""
    from . import journal, playbook

    records = journal.read_thread(thread)
    deltas = playbook.reflect(records, thread=thread)
    text = json.dumps(deltas, indent=2) + "\n"
    if out:
        Path(out).write_text(text)
        typer.echo(f"reflected: {len(deltas)} delta(s) from {len(records)} "
                   f"record(s) -> {out}", err=True)
    else:
        typer.echo(text, nl=False)
    raise typer.Exit(0)


@app.command("admit")
def admit_cmd(
    entry_id: str = typer.Argument(..., help="entry to admit for injection"),
    reason: str = typer.Option("", "--reason", help="why (journaled)"),
) -> None:
    """Admit an entry: only `admitted` entries may reach a prompt (cycle
    109's gate). Journaled (`playbook.admitted`)."""
    from . import journal, playbook

    cwd = Path.cwd()
    try:
        e = playbook.set_status(cwd, entry_id, "admitted",
                                reason=reason or "operator admit")
    except playbook.PlaybookError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from None
    try:
        journal.record(playbook.playbook_thread(cwd), "playbook.admitted",
                       tool="playbook", key=entry_id, status="admitted")
    except Exception:
        pass
    typer.echo(f"{entry_id}: admitted — it may now reach a prompt "
               f"(context = playbook)")
    raise typer.Exit(0)


@app.command("revoke")
def revoke_cmd(
    entry_id: str = typer.Argument(..., help="entry to remove"),
) -> None:
    """R-J revocation in ONE command: remove the entry — the next load
    cannot see it. Journaled (`playbook.revoked`)."""
    from . import journal, playbook

    cwd = Path.cwd()
    try:
        res = playbook.revoke(cwd, entry_id)
    except playbook.PlaybookError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from None
    try:
        journal.record(playbook.playbook_thread(cwd), "playbook.revoked",
                       tool="playbook", key=entry_id, status=f"was-{res['was']}")
    except Exception:
        pass
    typer.echo(f"{entry_id}: revoked (was {res['was']}) — removed; the next "
               f"load cannot see it")
    raise typer.Exit(0)
