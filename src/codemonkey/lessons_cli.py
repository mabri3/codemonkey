"""codemonkey lessons (loop13, cycle 45): run-history learning."""

from __future__ import annotations

import json
import typer

from .journal import class_summary, list_threads, read_thread
from .lessons import add, load_all, mark_verified, retrieve


app = typer.Typer(help="Lessons learned from run history.")


@app.command("list")
def lessons_list() -> None:
    entries = load_all()
    if not entries:
        typer.echo("(no lessons)")
        return
    for e in entries:
        mark = "verified" if e.get("verified") else "draft"
        typer.echo(f"{e['id']}  [{mark}]  ({e['tags']['tool']}, {e['tags']['error_class']})  {e['text'][:80]}")


@app.command("add")
def lessons_add(
    text: str = typer.Argument(help="The lesson text."),
    tool: str = typer.Option("*", "--tool"),
    error_class: str = typer.Option("*", "--error-class"),
    verified: bool = typer.Option(False, "--verified"),
) -> None:
    e = add(text, tool=tool, error_class=error_class, verified=verified)
    typer.echo(f"added {e['id']}")


@app.command("extract")
def lessons_extract(
    thread: str = typer.Argument(help="Journal thread to mine."),
    threshold: int = typer.Option(2, "--threshold"),
) -> None:
    """Mine journal failure-class counts into draft lessons."""
    summary = class_summary(read_thread(thread))
    if not summary:
        typer.echo("(empty journal)")
        return
    drafts = __import__("codemonkey.lessons", fromlist=["extract_drafts"]).extract_drafts(
        summary, threshold=threshold)
    if not drafts:
        typer.echo("(no class over threshold)")
        return
    for d in drafts:
        typer.echo(f"draft {d['id']} ({d['tags']['error_class']} x?) {d['text'][:70]}")


@app.command("verify")
def lessons_verify(lesson_id: str = typer.Argument(),
                   unverify: bool = typer.Option(False, "--unverify")) -> None:
    e = mark_verified(lesson_id, verified=not unverify)
    if e is None:
        typer.secho(f"no such lesson: {lesson_id}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    typer.echo(f"{lesson_id}: verified={e['verified']}")


@app.command("retrieve")
def lessons_retrieve(task: str = typer.Argument(help="Task text to scope by.")) -> None:
    for e in retrieve(task):
        typer.echo(json.dumps(e))
