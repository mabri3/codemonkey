"""`codemonkey branch` — git-worktree branches in .branches/ (loop38/80)."""

from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(no_args_is_help=True, help="Worktree branches in .branches/.")


def _wd() -> Path:
    return Path.cwd()


def _require_repo(wd: Path) -> None:
    from .branches import is_git_repo

    if not is_git_repo(wd):
        typer.secho(f"error: '{wd}' is not inside a git repository; "
                    "branch worktrees need one", err=True,
                    fg=typer.colors.RED)
        raise typer.Exit(2)


def _require_known(wd: Path, name: str) -> None:
    from .branches import branch_list

    if name not in branch_list(wd):
        typer.secho(f"error: no such branch '{name}' "
                    f"(known: {', '.join(branch_list(wd)) or 'none'})",
                    err=True, fg=typer.colors.RED)
        raise typer.Exit(2)


@app.command(name="create")
def branch_create_cmd(
    name: str = typer.Argument(help="Branch name (worktree at .branches/<name>)."),
    base: str = typer.Option("HEAD", "--base", help="Base ref for the new branch."),
) -> None:
    """Create branch/<name> as a worktree in .branches/<name>."""
    from .branches import branch_create

    wd = _wd()
    _require_repo(wd)
    r = branch_create(wd, name, base)
    if not r["ok"]:
        typer.secho(f"error: {r['detail']}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    typer.echo(f"branch {name} at {r['path']}")


@app.command(name="list")
def branch_list_cmd() -> None:
    """List branch worktrees."""
    from .branches import branch_list

    wd = _wd()
    _require_repo(wd)
    for name in branch_list(wd):
        typer.echo(name)


@app.command(name="diff")
def branch_diff_cmd(
    name: str = typer.Argument(help="Branch name to diff against HEAD."),
) -> None:
    """Show the --stat diff of branch/<name> vs HEAD."""
    from .branches import branch_diff

    wd = _wd()
    _require_repo(wd)
    _require_known(wd, name)
    out = branch_diff(wd, name)
    if out:
        typer.echo(out)


@app.command(name="remove")
def branch_remove_cmd(
    name: str = typer.Argument(help="Branch name to remove."),
) -> None:
    """Remove the .branches/<name> worktree and its branch ref."""
    from .branches import branch_remove

    wd = _wd()
    _require_repo(wd)
    _require_known(wd, name)
    r = branch_remove(wd, name)
    if not r["ok"]:
        typer.secho(f"error: {r['detail']}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    typer.echo(f"removed branch {name}")
