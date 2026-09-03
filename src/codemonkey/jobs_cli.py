"""codemonkey jobs (loop12, cycle 43): durable task files."""

from __future__ import annotations

import json
import typer

from .jobs import create, list_jobs, load, render, set_step

app = typer.Typer(help="Durable, resumable job files.")


@app.command("list")
def jobs_list() -> None:
    jobs = list_jobs()
    if not jobs:
        typer.echo("(no jobs)")
        return
    for j in jobs:
        done = sum(1 for s in j["steps"] if s["status"] == "done")
        typer.echo(f"{j['id']}  [{done}/{len(j['steps'])}]  {j['goal'][:70]}")


@app.command("create")
def jobs_create(
    goal: str = typer.Argument(help="The job goal."),
    steps: str = typer.Argument(help="Comma-separated step ids."),
) -> None:
    step_ids = [s.strip() for s in steps.split(",") if s.strip()]
    job = create(goal, step_ids)
    typer.echo(f"created {job['id']} ({len(step_ids)} steps)")


@app.command("show")
def jobs_show(job_id: str = typer.Argument()) -> None:
    job = load(job_id)
    if job is None:
        typer.secho(f"no such job: {job_id}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    typer.echo(render(job))


@app.command("done")
def jobs_done(job_id: str = typer.Argument(), step_id: str = typer.Argument(),
              note: str = typer.Option("", "--note")) -> None:
    job = set_step(job_id, step_id, "done", note)
    if job is None:
        typer.secho(f"no such job/step: {job_id}/{step_id}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)


@app.command("fail")
def jobs_fail(job_id: str = typer.Argument(), step_id: str = typer.Argument(),
              note: str = typer.Option("", "--note")) -> None:
    job = set_step(job_id, step_id, "failed", note)
    if job is None:
        typer.secho(f"no such job/step: {job_id}/{step_id}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
