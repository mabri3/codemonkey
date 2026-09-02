"""codemonkey CLI entry point (Typer app)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from . import __version__

app = typer.Typer(
    name="codemonkey",
    help=(
        "codemonkey — a scriptable coding-agent CLI for OpenAI-style and "
        "Anthropic-style endpoints (defaults to a local llama.cpp server)."
    ),
    no_args_is_help=False,
    add_completion=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"codemonkey {__version__}")
        raise typer.Exit(0)


@app.callback()
def _callback(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Print the version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """codemonkey CLI."""


@app.command()
def config(
    ignore_user_config: Annotated[
        bool,
        typer.Option(
            "--ignore-user-config",
            help="Skip ~/.codemonkey/config.yaml when computing the effective config.",
        ),
    ] = False,
) -> None:
    """Print the effective merged config (secrets masked)."""
    from .config import ConfigError, load_config, render_config

    try:
        cfg = load_config(cwd=Path.cwd(), ignore_user_config=ignore_user_config)
    except ConfigError as exc:
        typer.secho(f"error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from None
    typer.echo(render_config(cfg), nl=False)


def main() -> None:  # pragma: no cover - convenience
    app()


if __name__ == "__main__":
    main()
