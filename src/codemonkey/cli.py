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

    schema = None
    if output_schema is not None:
        from .schema import SchemaError, load_schema_file

        try:
            schema = load_schema_file(output_schema)
        except SchemaError as exc:
            typer.secho(f"error: {exc}", err=True, fg=typer.colors.RED)
            raise typer.Exit(2) from None
    # Note: run_exec re-loads + validates the schema inside (cheap); passing
    # the path keeps a single code path from flag to validation.
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
            output_schema=output_schema,
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


@app.command(name="sessions")
def sessions(  # noqa: A001 - command name shadows builtin intentionally
    json_out: Annotated[
        bool, typer.Option("--json", help="Emit one JSON object per session.")
    ] = False,
) -> None:
    """List persisted sessions (thread id, updated time, first prompt)."""
    import json as _json
    from datetime import datetime

    from .config import ConfigError, load_config
    from .sessions import get_store

    try:
        cfg = load_config(cwd=Path.cwd())
    except ConfigError as exc:
        typer.secho(f"error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from None
    items = get_store(cfg).list()
    for it in items:
        if json_out:
            typer.echo(_json.dumps(it))
        else:
            when = datetime.fromtimestamp(it["updated"]).strftime("%Y-%m-%d %H:%M")
            first = (it["first_prompt"] or "").replace("\n", " ")[:60]
            typer.echo(
                f"{it['thread_id']}  {when}  {it['provider']}/{it['model']}  "
                f"{it['n_messages']} msgs  {first}"
            )


def main() -> None:  # pragma: no cover - convenience
    _dispatch_exec_resume()
    app()


def _dispatch_exec_resume() -> None:
    """`codemonkey exec resume ...` is dispatched before Typer parses argv:
    click would treat `resume` as the (only) positional prompt argument and
    reject the remaining tokens. This shim handles only the resume form and
    leaves all other invocations untouched."""
    import sys

    argv = sys.argv[1:]
    if len(argv) >= 2 and argv[0] == "exec" and argv[1] == "resume":
        _exec_resume_main(argv[2:])
        raise SystemExit(0)


def _exec_resume_main(args: list) -> None:
    """Parse a small, explicit subset of exec flags for the resume form:
    --json / -o FILE / --ephemeral / --skip-git-repo-check / --provider /
    --model; positionals: [--last|THREAD_ID] [PROMPT] (any order; words after
    the thread spec become the prompt)."""
    import sys
    from .config import ConfigError, load_config
    from .exec import ExecUsageError, run_exec
    from .providers.base import AuthError, ProviderError
    from .sessions import get_store

    json_out = False
    output_last_message = None
    ephemeral = False
    skip_git = False
    provider = None
    model = None
    positionals: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--json":
            json_out = True
        elif a in ("-o", "--output-last-message"):
            i += 1
            if i >= len(args):
                print("error: -o/--output-last-message needs a value", file=sys.stderr)
                raise SystemExit(2)
            output_last_message = Path(args[i])
        elif a == "--ephemeral":
            ephemeral = True
        elif a == "--skip-git-repo-check":
            skip_git = True
        elif a == "--provider":
            i += 1
            provider = args[i] if i < len(args) else None
        elif a == "--model":
            i += 1
            model = args[i] if i < len(args) else None
        else:
            positionals.append(a)
        i += 1

    thread_spec = positionals[0] if positionals else "--last"
    prompt = " ".join(positionals[1:]) or None
    if prompt is None:
        import sys as _sys

        if not _sys.stdin.isatty():
            prompt = _sys.stdin.read().rstrip("\n")

    try:
        cfg = load_config(cwd=Path.cwd())
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)

    store = get_store(cfg)
    if thread_spec in ("--last", "last"):
        thread_id = store.latest()
        if thread_id is None:
            print("error: no persisted sessions to resume (--last)", file=sys.stderr)
            raise SystemExit(2)
    else:
        thread_id = thread_spec

    try:
        code = run_exec(
            prompt,
            json_mode=json_out,
            resume_thread=thread_id,
            ephemeral=ephemeral,
            skip_git_repo_check=skip_git,
            provider_name=provider,
            model=model,
            output_last_message=output_last_message,
        )
    except ExecUsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
    except AuthError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
    except ProviderError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
