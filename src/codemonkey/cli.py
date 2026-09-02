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


@app.command()
def exec(
    prompt: Annotated[
        Optional[str],
        typer.Argument(
            help="Prompt text, or '-' to read the whole prompt from stdin.",
        ),
    ] = None,
    json_out: Annotated[
        bool,
        typer.Option("--json", help="Emit the JSONL event stream on stdout."),
    ] = False,
    output_last_message: Annotated[
        Optional[Path],
        typer.Option("-o", "--output-last-message", help="Also write the final message to FILE."),
    ] = None,
    output_schema: Annotated[
        Optional[Path],
        typer.Option("--output-schema", help="JSON Schema file; validate the final response (one retry)."),
    ] = None,
    sandbox: Annotated[
        Optional[str],
        typer.Option("--sandbox", help="read-only | workspace-write | danger-full-access"),
    ] = None,
    ask_for_approval: Annotated[
        Optional[str],
        typer.Option("-a", "--ask-for-approval", help="untrusted | on-request | never"),
    ] = None,
    provider: Annotated[
        Optional[str],
        typer.Option("--provider", help="Provider name from config."),
    ] = None,
    model: Annotated[
        Optional[str],
        typer.Option("--model", help="Model id override for the active provider."),
    ] = None,
    cd: Annotated[
        Optional[Path],
        typer.Option("-C", "--cd", help="Working directory for the run."),
    ] = None,
    add_dir: Annotated[
        Optional[list[str]],
        typer.Option("--add-dir", help="Extra writable roots (repeatable)."),
    ] = None,
    skip_git_repo_check: Annotated[
        bool,
        typer.Option("--skip-git-repo-check", help="Allow running outside a git repo."),
    ] = False,
    ephemeral: Annotated[
        bool,
        typer.Option("--ephemeral", help="Do not persist the session."),
    ] = False,
    max_turns: Annotated[
        Optional[int],
        typer.Option("--max-turns", help="Maximum agent loop turns."),
    ] = None,
    timeout: Annotated[
        Optional[int],
        typer.Option("--timeout", help="Shell/tool timeout in seconds."),
    ] = None,
    dangerously_bypass: Annotated[
        bool,
        typer.Option(
            "--dangerously-bypass-approvals-and-sandbox",
            help="Lift sandbox + approval policy entirely.",
        ),
    ] = False,
    ignore_user_config: Annotated[
        bool,
        typer.Option("--ignore-user-config", help="Skip ~/.codemonkey/config.yaml."),
    ] = False,
) -> None:
    """Non-interactive exec: run the agent once, print the final response.

    stdout (text mode) carries ONLY the final response; diagnostics go to
    stderr. With --json, stdout carries ONLY the JSONL event stream.
    """
    from .exec import ExecUsageError, run_exec
    from .providers.base import AuthError, ProviderError

    if output_schema is not None:
        typer.secho(
            "error: --output-schema is wired in cycle 6 (structured output)",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(2)
    try:
        code = run_exec(
            prompt,
            json_mode=json_out,
            cwd=cd,
            add_dirs=add_dir or [],
            sandbox=sandbox,
            approval=ask_for_approval,
            provider_name=provider,
            model=model,
            skip_git_repo_check=skip_git_repo_check,
            ephemeral=ephemeral,
            max_turns=max_turns,
            timeout=timeout,
            output_last_message=output_last_message,
            ignore_user_config=ignore_user_config,
            bypass=dangerously_bypass,
        )
    except ExecUsageError as exc:
        typer.secho(f"error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from None
    except AuthError as exc:
        typer.secho(f"error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from None
    except ProviderError as exc:
        typer.secho(f"error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1) from None
    except KeyboardInterrupt:
        typer.secho("interrupted", err=True)
        raise typer.Exit(1) from None
    raise typer.Exit(code)


def main() -> None:  # pragma: no cover - convenience
    app()


if __name__ == "__main__":
    main()
