"""codemonkey journal (loop7, cycle 33): execution-journal forensics."""

from __future__ import annotations

import json

import typer

from .journal import class_summary, list_threads, read_thread

app = typer.Typer(help="Execution-journal forensics.")


@app.command("list")
def journal_list() -> None:
    """List thread ids that have journals."""
    for tid in list_threads():
        typer.echo(tid)


@app.command("tail")
def journal_tail(
    thread: str = typer.Argument(help="Thread id."),
    n: int = typer.Option(10, "--last", help="Records to show."),
) -> None:
    """Show the last N journal records for a thread."""
    recs = read_thread(thread)
    for rec in recs[-n:]:
        typer.echo(json.dumps(rec))


@app.command("show")
def journal_show(thread: str = typer.Argument(help="Thread id.")) -> None:
    """Full journal + failure-class summary for a thread."""
    recs = read_thread(thread)
    if not recs:
        typer.secho(f"no journal for thread {thread}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    for rec in recs:
        typer.echo(json.dumps(rec))
    summary = class_summary(recs)
    typer.echo("-- class summary --")
    for cls, count in sorted(summary.items()):
        typer.echo(f"  {cls}: {count}")
    # loop39 cycle 88: taxonomy rows beside the class summary
    from .failclass import summarize_taxonomy

    tax = summarize_taxonomy(recs)
    if tax:
        typer.echo("-- failure taxonomy --")
        for cat, count in sorted(tax.items()):
            typer.echo(f"  {cat}: {count}")
