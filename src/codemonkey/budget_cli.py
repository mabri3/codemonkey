"""codemonkey budget (loop19, cycle 56)."""

from __future__ import annotations

import typer

from .budget import (render_yaml, safe_context_limit, validate_budget)

app = typer.Typer(help="VRAM→tokens context budget calculator.")


@app.command("show")
def budget_show(
    vram_gb: float = typer.Option(..., "--vram-gb", help="VRAM headroom for KV cache."),
    layers: int = typer.Option(None, "--layers"),
    kv_heads: int = typer.Option(None, "--kv-heads"),
    head_dim: int = typer.Option(None, "--head-dim"),
) -> None:
    err = validate_budget(vram_gb, layers, kv_heads, head_dim)
    if err:
        typer.secho(err, err=True, fg=typer.colors.RED)
        raise typer.Exit(1)
    kwargs = {}
    if layers is not None:
        kwargs = {"layers": layers, "kv_heads": kv_heads, "head_dim": head_dim}
    rec = safe_context_limit(vram_headroom_gb=vram_gb, **kwargs)
    typer.echo(f"kv bytes/token: {rec['kv_bytes_per_token']}")
    typer.echo(f"usable for KV: {rec['usable_gb']} GB")
    typer.echo(f"safe context_limit: {rec['max_tokens']}")
    typer.echo(f"observation_budget (40%): {rec['observation_budget']}")
    typer.echo("--- copiable ---")
    typer.echo(render_yaml(rec))
