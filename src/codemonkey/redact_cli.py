"""codemonkey redact (loop16, cycle 49): secret-redaction repair pass."""

from __future__ import annotations

import typer

from .config import load_config
from .journal import list_threads, journal_path
from .redact import needles_from_config, redact_eval_results, redact_journal_file

app = typer.Typer(help="Redact configured secrets from durable stores.")


@app.command("run")
def redact_run(
    eval_dir: typer.Path = typer.Option("build/eval", help="Eval results dir."),
) -> None:
    """Scan journal + eval results for configured API key values and
    key-shaped strings; replace with [REDACTED]."""
    cfg = load_config(cwd=None, ignore_user_config=False)
    needles = needles_from_config(cfg)
    if not needles:
        typer.echo("no secret needles configured (nothing to redact)")
        return
    total = 0
    for tid in list_threads():
        p = journal_path(tid)
        if p.is_file():
            n = redact_journal_file(p, needles)
            if n:
                typer.echo(f"journal {tid}: {n} redaction(s)")
                total += n
    ep = eval_dir / "results.json"
    if ep.is_file():
        import json as _json

        from .eval import _score_task  # noqa: F401 (ensure module loads)

        data = _json.loads(ep.read_text())
        data, n = redact_eval_results(data, needles)
        if n:
            ep.write_text(_json.dumps(data, indent=2))
            typer.echo(f"eval results: {n} redaction(s)")
            total += n
    typer.echo(f"redaction complete: {total} hit(s) replaced")
