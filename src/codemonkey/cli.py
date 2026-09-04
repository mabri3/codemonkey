"""codemonkey CLI entry point (Typer app)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import json
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


@app.callback(invoke_without_command=True)
def _callback(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Print the version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
    provider: Annotated[
        str,
        typer.Option("--provider", "-p", help="Provider for the interactive session."),
    ] = "",
    model: Annotated[
        str,
        typer.Option("--model", "-m", help="Model override for the interactive session."),
    ] = "",
    sandbox: Annotated[
        str,
        typer.Option("--sandbox", help="Sandbox level for the session (read-only | workspace-write | danger-full-access)."),
    ] = "",
    approval: Annotated[
        str,
        typer.Option("--ask-for-approval", "--approval", "-a", help="Approval policy (untrusted | on-request | never)."),
    ] = "",
    add_dir: Annotated[
        list[str],
        typer.Option("--add-dir", "-C", help="Additional writable directory (repeatable)."),
    ] = [],
    max_turns: Annotated[
        int,
        typer.Option("--max-turns", help="Max agent turns per prompt."),
    ] = 0,
    timeout: Annotated[
        int,
        typer.Option("--timeout", help="Per-tool timeout seconds."),
    ] = 0,
    ignore_user_config: Annotated[
        bool,
        typer.Option("--ignore-user-config", help="Skip ~/.codemonkey/config.yaml."),
    ] = False,
    bypass: Annotated[
        bool,
        typer.Option(
            "--dangerously-bypass-approvals-and-sandbox",
            help="Lift the sandbox and approval gates entirely.",
        ),
    ] = False,
    show_reasoning: Annotated[
        bool,
        typer.Option("--show-reasoning", help="Print model reasoning blocks in the REPL."),
    ] = False,
    ephemeral: Annotated[
        bool,
        typer.Option("--ephemeral", help="Do not persist this session."),
    ] = False,
) -> None:
    """codemonkey CLI. Run with no subcommand for the interactive REPL."""
    if ctx.invoked_subcommand is None:
        overrides = {}
        if max_turns:
            overrides["max_turns"] = max_turns
        if timeout:
            overrides["timeout_seconds"] = timeout
        if add_dir:
            overrides["add_dirs"] = list(add_dir)
        from .config import ConfigError, load_config

        try:
            cfg = load_config(
                cwd=Path.cwd(),
                overrides=overrides or None,
                ignore_user_config=ignore_user_config,
            )
        except ConfigError as exc:
            typer.secho(f"error: {exc}", err=True, fg=typer.colors.RED)
            raise typer.Exit(2) from None
        if model:
            cfg.setdefault("providers", {}).setdefault(
                provider or cfg.get("default_provider", "local"), {}
            )["model"] = model
        from .repl import run_repl

        code = run_repl(
            cfg,
            provider_name=provider,
            show_reasoning=show_reasoning,
            approval=approval,
            sandbox=sandbox,
            bypass=bypass,
            ephemeral=ephemeral,
        )
        raise typer.Exit(code)


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
def review(
    uncommitted: Annotated[
        bool,
        typer.Option("--uncommitted", help="Review uncommitted changes vs HEAD (default)."),
    ] = True,
    base: Annotated[
        str,
        typer.Option("--base", help="Review the diff vs this base ref instead of HEAD."),
    ] = "",
    staged: Annotated[
        bool,
        typer.Option("--staged", help="Review only the staged changes."),
    ] = False,
    provider_name: Annotated[
        str,
        typer.Option("--provider", "-p", help="Provider to use (defaults to configured default)."),
    ] = "",
) -> None:
    """LLM review of the repo's uncommitted diff (read-only)."""
    from .config import ConfigError, load_config, resolve_api_key
    from .providers import ProviderError, build_provider
    from . import review as review_mod

    cwd = Path.cwd()
    try:
        cfg = load_config(cwd=cwd)
        name = provider_name or cfg.get("default_provider", "local")
        pconf = cfg.get("providers", {}).get(name)
        if pconf is None:
            typer.secho(
                f"error: unknown provider '{name}'. "
                f"Valid providers: {', '.join(cfg['providers'])}",
                err=True, fg=typer.colors.RED,
            )
            raise typer.Exit(2)
        prov = build_provider(
            protocol=pconf.get("protocol", "openai"),
            base_url=pconf["base_url"],
            model=pconf.get("model", ""),
            api_key=resolve_api_key(cfg, name) or "",
        )
        text = review_mod.run_review(
            prov, cwd,
            base=(base or None),
            staged=staged,
            on_event=lambda ev: None,
        )
    except ConfigError as exc:
        typer.secho(f"error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from None
    except RuntimeError as exc:
        typer.secho(f"error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from None
    except ProviderError as exc:
        typer.secho(f"error: provider failure: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1) from None
    typer.echo(text)


@app.command()
def graph(
    symbol: Annotated[
        str,
        typer.Argument(help="Symbol/file/concept to look up in graphify-out/."),
    ],
    to: Annotated[
        Optional[str],
        typer.Option("--to", help="With --path: end symbol of the relation path."),
    ] = None,
    max_results: Annotated[
        int,
        typer.Option("--max-results", help="Maximum edges to print."),
    ] = 20,
) -> None:
    """Print code-graph facts for SYMBOL from graphify-out/ (no model needed).

    Plain lookup: nodes matching the symbol + their edges. With `--to SYM2`:
    the shortest relation path SYMBOL -> SYM2. Reports `[stale]` in-band when
    the graph is older than HEAD; refuses honestly when there is no graph.
    """
    from . import graphquery
    from .tools.graph import _check_staleness

    cwd = Path.cwd()
    gdir = graphquery.find_graph_dir(cwd)
    if gdir is None:
        typer.secho("error: no graphify-out/ graph in this workspace "
                    "(build one with `graphify .`)", err=True, fg=typer.colors.RED)
        raise typer.Exit(2)
    stale = _check_staleness(gdir, cwd)
    if stale:
        typer.secho(stale, err=True, fg=typer.colors.YELLOW)
    graph = graphquery.load_graph(gdir)
    if to:
        from .tools.graph import graph_path_lookup

        res = graph_path_lookup(cwd, symbol, to, max_depth=6)
        if not res["ok"]:
            typer.secho(f"error: {res['error']}", err=True, fg=typer.colors.RED)
            raise typer.Exit(1)
        typer.echo("path: " + " -> ".join(res["path"]))
        return
    res = graphquery.graph_query(graph, symbol, max_results=max_results)
    if not res["matches"]:
        typer.echo(f"(no node matches '{symbol}')")
        raise typer.Exit(1)
    for nid, n in list(res["matches"].items())[:10]:
        src = n.get("src", n.get("loc", ""))
        label = n.get("label", n.get("name", ""))
        line = nid + (f" [{label}]" if label and label != nid else "")
        if src:
            line += f" ({src})"
        typer.echo(line)
    for e in res["edges"][:max_results]:
        rel = e.get("relation", e.get("type", ""))
        typer.echo(f"- {e.get('source', '?')} -> {e.get('target', '?')}"
                   + (f" [{rel}]" if rel else ""))


@app.command()
def undo(
    list_only: Annotated[
        bool,
        typer.Option("--list", help="List checkpoints without restoring."),
    ] = False,
) -> None:
    """Undo: restore the most recent checkpoint (files snapshotted pre-mutation)."""
    from . import checkpoints as cp_mod

    cwd = Path.cwd()
    if list_only:
        cps = cp_mod.list_checkpoints(workdir=cwd)  # 14F2: this workspace only
        if not cps:
            typer.echo("(no checkpoints)")
            return
        for c in cps[:10]:
            import datetime
            ts = datetime.datetime.fromtimestamp(c["ts"]).strftime("%m-%d %H:%M:%S")
            typer.echo(f"{ts}  {len(c['files'])} file(s): " + ", ".join(c["files"][:4])
                       + (" ..." if len(c["files"]) > 4 else ""))
        return
    try:
        result = cp_mod.restore_latest(cwd)
    except LookupError as exc:
        typer.secho(f"error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1) from None
    except OSError as exc:
        typer.secho(f"error: restore failed: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1) from None
    typer.echo(f"restored {len(result['restored'])} file(s) from checkpoint")
    for rel in result["restored"]:
        typer.echo(f"  {rel}")


@app.command()
def eval(
    suite: Annotated[
        Path,
        typer.Argument(help="Path to the YAML golden suite."),
    ],
    check: Annotated[
        bool,
        typer.Option("--check", help="Compare against the baseline; exit 1 on regression."),
    ] = False,
    baseline: Annotated[
        Path,
        typer.Option("--baseline", help="Baseline JSON path (default build/eval/baseline.json)."),
    ] = Path("build/eval/baseline.json"),
    out_dir: Annotated[
        Path,
        typer.Option("--out", help="Results output dir (default build/eval)."),
    ] = Path("build/eval"),
    write_baseline: Annotated[
        bool,
        typer.Option("--write-baseline", help="Write the current run as the new baseline."),
    ] = False,
    strategy_matrix: Annotated[
        str,
        typer.Option("--strategy-matrix", help="Comma-separated compaction strategies to bake off (runs the suite once per strategy)."),
    ] = "",
    delegation_matrix: Annotated[
        bool,
        typer.Option("--delegation-matrix", help="Bake off delegation off vs on (implementer role)."),
    ] = False,
    route_stats_flag: Annotated[
        bool,
        typer.Option("--route-stats", help="Print per-route pass_rate/token aggregates from the last results."),
    ] = False,
    early_stop: Annotated[
        bool,
        typer.Option("--early-stop", help="Stop the suite when the hoeffding-gate certificate settles (loop38)."),
    ] = False,
    delta: Annotated[
        float,
        typer.Option("--delta", help="Gate level for --early-stop (default 0.05)."),
    ] = 0.05,
) -> None:
    """Run a golden evaluation suite against the real exec path."""
    if delegation_matrix:
        from .matrix import run_delegation_matrix

        results = run_delegation_matrix(suite, out_dir=out_dir)
        typer.echo(json.dumps(results["arms"], indent=2))
        typer.echo(f"matrix written: {Path(out_dir) / 'delegation_matrix.json'}")
        return
    if strategy_matrix:
        from .matrix import render_table, run_matrix

        strats = [s.strip() for s in strategy_matrix.split(",") if s.strip()]
        results = run_matrix(suite, strats, out_dir=out_dir)
        typer.echo(render_table(results))
        typer.echo(f"matrix written: {Path(out_dir) / 'matrix.json'}")
        return
    from .eval import check_regression as _check_regression
    from .eval import run_suite as _run_suite
    from .eval import write_baseline as _write_baseline

    results = _run_suite(suite, out_dir=out_dir, early_stop=early_stop, delta=delta)
    if route_stats_flag:
        from .routing import route_stats as _rs

        typer.echo(json.dumps(_rs(results), indent=2))
    typer.echo(f"suite: {results['suite']}  pass_rate: {results['pass_rate']}  "
               f"tokens: {results['total_tokens']}  wall: {results['wall_seconds']}s")
    cert = results.get("certificate") or {}
    if cert.get("certified_pass") is not None:
        verdict = "pass" if cert["certified_pass"] else "fail"
        typer.echo(f"certificate: {verdict} {cert.get('kind', 'hoeffding-gate')} "
                   f"at_n={cert.get('at_n')} ran={cert.get('total')} delta={delta} "
                   f"stopped_early={results.get('stopped_early', False)}")
    for t in results["tasks"]:
        mark = "PASS" if t["ok"] else "FAIL"
        typer.echo(f"  [{mark}] {t['id']}")
        if not t["ok"]:
            typer.echo(f"         {json.dumps(t.get('detail', {}))}")
    if write_baseline:
        _write_baseline(results, baseline)
        typer.echo(f"baseline written: {baseline}")
        return
    ok, regressions = _check_regression(results, baseline)
    if not ok:
        typer.secho("REGRESSIONS:", err=True, fg=typer.colors.RED)
        for r in regressions:
            typer.echo(f"  {r}")
        raise typer.Exit(1)
    typer.echo("no regressions")


journal_app = typer.Typer()
try:
    from .journal_cli import app as _journal_app

    app.add_typer(_journal_app, name="journal", help="Execution-journal forensics.")
except ImportError:  # pragma: no cover
    pass
try:
    from .jobs_cli import app as _jobs_app

    app.add_typer(_jobs_app, name="jobs", help="Durable, resumable job files.")
except ImportError:  # pragma: no cover
    pass
try:
    from .lessons_cli import app as _lessons_app

    app.add_typer(_lessons_app, name="lessons", help="Lessons learned from run history.")
except ImportError:  # pragma: no cover
    pass
try:
    from .redact_cli import app as _redact_app

    app.add_typer(_redact_app, name="redact", help="Secret-redaction repair pass.")
except ImportError:  # pragma: no cover
    pass
try:
    from .budget_cli import app as _budget_app

    app.add_typer(_budget_app, name="budget", help="VRAM→tokens budget calculator.")
except ImportError:  # pragma: no cover
    pass
try:
    from .digest_cli import digest_cmd

    app.command(name="digest", help="Plain-text digest of one run (thread).")(digest_cmd)
    from .rules_cli import rules_compile

    app.command(name="rules-compile", help="Journal failures → draft permission rules.")(rules_compile)
except ImportError:  # pragma: no cover
    pass


@app.command()
def status(
    json_out: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Operator surface: aggregate jobs/journal/sessions/eval/cost/spill."""
    from .status_mod import collect, render

    data = collect(Path("build/eval").resolve())
    if json_out:
        typer.echo(json.dumps(data, indent=2))
    else:
        typer.echo(render(data))


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
        # 51F2: the run's event stream already printed this line; printing it
        # again here is what made every transport failure report twice.
        if not getattr(exc, "reported", False):
            typer.secho(f"error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1) from None

    if json_out:
        for n in names:
            typer.echo(_json.dumps({"model": n, "provider": name}))
    else:
        for n in names:
            typer.echo(n)


class _ExecTyperGroup(typer.core.TyperGroup):
    """Exec group: `resume` is the ONLY real subcommand. Everything else after
    the group's own params is prompt-mode input (this group doubles as the
    `exec [PROMPT]` default command), so unknown first tokens fall through to
    `invoke_without_command` instead of failing with "No such command"."""

    def resolve_command(self, ctx, args):  # noqa: ANN001
        try:
            return super().resolve_command(ctx, args)
        except Exception:
            # Fall through to prompt mode: make the resolution look empty so
            # invoke()'s `if not ctx._protected_args` branch runs the
            # invoke_without_command path with the group's parsed values.
            ctx._protected_args = []
            ctx.args = []
            ctx.invoked_subcommand = None
            return "", None, []


exec_app = typer.Typer(
    name="exec",
    invoke_without_command=True,
    no_args_is_help=False,
    # allow_interspersed_args=False: the group parser STOPS at the subcommand
    # token (`resume`), leaving [thread, PROMPT, resume-flags...] in the
    # command stream so the subcommand sees its full own flag set
    # (MultiCommand base behavior requires this once the group takes args).
    # ignore_unknown_options keeps unparsable leftovers in ctx.args.
    context_settings={
        "ignore_unknown_options": True,
        "allow_extra_args": True,
        "allow_interspersed_args": False,
    },
    help=(
        "Non-interactive exec: run the agent once, print the final response. "
        "Use `exec resume [--last|THREAD_ID] [PROMPT]` to continue a session."
    ),
)
app.add_typer(exec_app, name="exec", cls=_ExecTyperGroup)
_EXEC_FLAG_NAMES = (
    "--json", "--output-last-message", "--output-schema", "--sandbox",
    "--ask-for-approval", "--provider", "--model", "--cd", "--add-dir",
    "--skip-git-repo-check", "--ephemeral", "--max-turns", "--timeout",
    "--dangerously-bypass-approvals-and-sandbox", "--ignore-user-config",
    "-o", "-a", "-C",
)


@exec_app.callback()
def exec(
    ctx: typer.Context,
    prompt: Annotated[
        Optional[list[str]],
        typer.Argument(
            help=(
                "Prompt text (quoted string recommended; unquoted words are "
                "joined), or '-' to read the whole prompt from stdin."
            ),
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
        typer.Option("-a", "--ask-for-approval", "--approval", help="untrusted | on-request | never"),
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
    no_project_instructions: Annotated[
        bool,
        typer.Option(
            "--no-project-instructions",
            help="Skip AGENTS.md/CLAUDE.md project-instruction loading for this run.",
        ),
    ] = False,
    cost_summary: Annotated[
        bool,
        typer.Option("--cost-summary", help="Print a token/cost summary to stderr after the run."),
    ] = False,
    job: Annotated[
        str,
        typer.Option("--job", help="Durable job id: inject goal/steps, persist JOB_STEP transitions."),
    ] = "",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Preview mutating tool calls without executing."),
    ] = False,
    ignore_user_config: Annotated[
        bool,
        typer.Option("--ignore-user-config", help="Skip ~/.codemonkey/config.yaml."),
    ] = False,
) -> None:
    """Non-interactive exec: run the agent once, print the final response.

    stdout (text mode) carries ONLY the final response; diagnostics go to
    stderr. With --json, stdout carries ONLY the JSONL event stream.
    `codemonkey exec resume ...` is pre-dispatched to the real `resume`
    subcommand before Typer parsing (see _dispatch_exec_resume / main).
    """
    if ctx.invoked_subcommand is not None:
        return  # a real subcommand (resume) handles itself
    prompt = " ".join(list(prompt or [])) or None
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
            project_instructions=(False if no_project_instructions else None),
            cost_summary=cost_summary,
            job_id=job,
            dry_run=dry_run,
        )
    except ExecUsageError as exc:
        typer.secho(f"error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from None
    except AuthError as exc:
        typer.secho(f"error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from None
    except ProviderError as exc:
        # 51F2: the run's event stream already printed this line; printing it
        # again here is what made every transport failure report twice.
        if not getattr(exc, "reported", False):
            typer.secho(f"error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1) from None
    except KeyboardInterrupt:
        typer.secho("interrupted", err=True)
        raise typer.Exit(1) from None
    raise typer.Exit(code)


def _run_exec_or_exit(prompt, **kwargs) -> None:
    """Shared tail for exec + exec resume: run_exec with the CLI's exit-code
    mapping (usage/auth → 2, provider → 1, success code → typer.Exit)."""
    from .exec import ExecUsageError, run_exec
    from .providers.base import AuthError, ProviderError

    try:
        code = run_exec(prompt, **kwargs)
    except ExecUsageError as exc:
        typer.secho(f"error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from None
    except AuthError as exc:
        typer.secho(f"error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from None
    except ProviderError as exc:
        # 51F2: the run's event stream already printed this line; printing it
        # again here is what made every transport failure report twice.
        if not getattr(exc, "reported", False):
            typer.secho(f"error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1) from None
    except KeyboardInterrupt:
        typer.secho("interrupted", err=True)
        raise typer.Exit(1) from None
    raise typer.Exit(code)


@exec_app.command(name="resume")
def exec_resume(
    thread: Annotated[
        str,
        typer.Argument(help="Thread id to resume, or '--last' for the most recent."),
    ] = "--last",
    prompt: Annotated[
        Optional[str],
        typer.Argument(help="Follow-up prompt (falls back to piped stdin)."),
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
        typer.Option("-a", "--ask-for-approval", "--approval", help="untrusted | on-request | never"),
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
    """Continue a persisted session (same flag set as `exec`)."""
    _resume_dispatch(
        thread=thread,
        prompt=prompt,
        json_out=json_out,
        output_last_message=output_last_message,
        output_schema=output_schema,
        sandbox=sandbox,
        ask_for_approval=ask_for_approval,
        provider=provider,
        model=model,
        cd=cd,
        add_dir=add_dir,
        skip_git_repo_check=skip_git_repo_check,
        ephemeral=ephemeral,
        max_turns=max_turns,
        timeout=timeout,
        dangerously_bypass=dangerously_bypass,
        ignore_user_config=ignore_user_config,
    )


def _resume_dispatch(
    *,
    thread: str,
    prompt: Optional[str],
    json_out: bool,
    output_last_message: Optional[Path],
    output_schema: Optional[Path],
    sandbox: Optional[str],
    ask_for_approval: Optional[str],
    provider: Optional[str],
    model: Optional[str],
    cd: Optional[Path],
    add_dir: Optional[list],
    skip_git_repo_check: bool,
    ephemeral: bool,
    max_turns: Optional[int],
    timeout: Optional[int],
    dangerously_bypass: bool,
    ignore_user_config: bool,
) -> None:
    """Shared resume implementation for the `exec resume` surface: the exec
    group's real `resume` subcommand and the hidden top-level `exec-resume`
    landing command (the _dispatch_exec_resume argv rewrite) both end here."""
    import sys

    from .config import ConfigError, load_config
    from .sessions import get_store

    if thread in _EXEC_FLAG_NAMES:
        # A leading `--flag VALUE` after `resume` would be swallowed into the
        # thread slot by the group parse; normalize to `--last`.
        thread = "--last"

    if prompt is None and not sys.stdin.isatty():
        prompt = sys.stdin.read().rstrip("\n")

    try:
        cfg = load_config(cwd=Path(cd).resolve() if cd else Path.cwd())
    except ConfigError as exc:
        typer.secho(f"error: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(2) from None

    store = get_store(cfg)
    if thread == "--last":
        thread_id = store.latest()
        if thread_id is None:
            typer.secho(
                "error: no persisted sessions to resume (--last)",
                err=True,
                fg=typer.colors.RED,
            )
            raise typer.Exit(2)
    else:
        thread_id = thread

    _run_exec_or_exit(
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
        resume_thread=thread_id,
        max_turns=max_turns,
        timeout=timeout,
        output_last_message=output_last_message,
        output_schema=output_schema,
        ignore_user_config=ignore_user_config,
        bypass=dangerously_bypass,
    )


@app.command(name="exec-resume", hidden=True)
def exec_resume_alias(
    thread: Annotated[
        str,
        typer.Argument(help="Thread id to resume, or '--last' for the most recent."),
    ] = "--last",
    prompt: Annotated[
        Optional[str],
        typer.Argument(help="Follow-up prompt (falls back to piped stdin)."),
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
        typer.Option("-a", "--ask-for-approval", "--approval", help="untrusted | on-request | never"),
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
    """Hidden landing command for `codemonkey exec resume ...` after the
    _dispatch_exec_resume argv rewrite. Shares the full exec flag set."""
    _resume_dispatch(
        thread=thread,
        prompt=prompt,
        json_out=json_out,
        output_last_message=output_last_message,
        output_schema=output_schema,
        sandbox=sandbox,
        ask_for_approval=ask_for_approval,
        provider=provider,
        model=model,
        cd=cd,
        add_dir=add_dir,
        skip_git_repo_check=skip_git_repo_check,
        ephemeral=ephemeral,
        max_turns=max_turns,
        timeout=timeout,
        dangerously_bypass=dangerously_bypass,
        ignore_user_config=ignore_user_config,
    )


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
    """`codemonkey exec resume ...` rewrites argv to `codemonkey exec-resume ...`
    BEFORE Typer parses it. Click would otherwise treat `resume` as the exec
    (default) command's prompt positional and reject the resume-specific
    positionals/flags. Forwarded verbatim -- Click parses the full flag set as
    the ordinary `resume` subcommand, including `--help`."""
    import sys

    argv = sys.argv[1:]
    if len(argv) >= 2 and argv[0] == "exec" and argv[1] == "resume":
        sys.argv = [sys.argv[0], "exec-resume", *argv[2:]]


if __name__ == "__main__":
    main()
