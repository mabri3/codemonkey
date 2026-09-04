"""codemonkey digest (loop21, cycle 58)."""

from __future__ import annotations

import json
import typer

from .digest import build_digest, render_digest


def digest_cmd(
    thread_id: str = typer.Argument(help="Journal thread id."),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Plain-text narrative of one run: tools, failures, flags."""
    d = build_digest(thread_id)
    if json_out:
        typer.echo(json.dumps(d, indent=2))
    else:
        typer.echo(render_digest(d))
