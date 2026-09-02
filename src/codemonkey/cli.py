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


def _cfg() -> dict:
    from .config import ConfigError, load_config

    try:
        return load_config(cwd=Path.cwd())
    except ConfigError as exc:
        typer.secho(f"error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from None


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


@app.command()
def models(
    provider: Annotated[
        str,
        typer.Option(
            "--provider",
            help="Provider name to query (defaults to the configured default).",
        ),
    ] = "",
    json_out: Annotated[
        bool,
        typer.Option("--json", help="Emit JSON (one object per line)."),
    ] = False,
) -> None:
    """List models exposed by a provider endpoint."""
    import json as _json

    from .config import ConfigError, load_config, resolve_api_key
    from .providers import AuthError, ProviderError, build_provider

    try:
        cfg = load_config(cwd=Path.cwd())
        name = provider or cfg.get("default_provider", "local")
        pconf = cfg.get("providers", {}).get(name)
        if pconf is None:
            typer.secho(
                f"error: unknown provider '{name}'. "
                f"Valid providers: {', '.join(cfg['providers'])}",
                err=True,
                fg=typer.colors.RED,
            )
            raise typer.Exit(2)
        prov = build_provider(
            protocol=pconf.get("protocol", "openai"),
            base_url=pconf["base_url"],
            model=pconf.get("model", ""),
            api_key=resolve_api_key(cfg, name),
            timeout=float(cfg.get("timeout_seconds", 300)),
        )
        try:
            names = prov.list_models()
        finally:
            prov.close()
    except ConfigError as exc:
        typer.secho(f"error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from None
    except AuthError as exc:
        typer.secho(f"error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from None
    except ProviderError as exc:
        typer.secho(f"error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1) from None

    if json_out:
        for n in names:
            typer.echo(_json.dumps({"model": n, "provider": name}))
    else:
        for n in names:
            typer.echo(n)


def main() -> None:  # pragma: no cover - convenience
    app()


if __name__ == "__main__":
    main()
