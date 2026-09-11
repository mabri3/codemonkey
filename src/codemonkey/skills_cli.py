"""`codemonkey skills` — the operator surface for the quarantined store.

Cycle 82 ships `list` (honest empty when no store exists — a missing store is
not an error). The revocation verbs (`show`, `revoke`, `disable`, cycle 86)
land beside it; the stratey surfaces that LOAD admitted skills are cycle 84.
"""

from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(help="Skill library: quarantined store (list; revoke in a later cycle).")


@app.command("list")
def list_cmd() -> None:
    """List every skill in the workspace store with its status.

    Exit 0 on an empty or missing store (honest empty); an invalid manifest
    is shown as `invalid` with its reason rather than hidden."""
    from . import skills

    cwd = Path.cwd()
    rows = skills.list_skills(cwd)
    if not rows:
        typer.echo(f"no skills installed ({skills.store_root(cwd)})")
        raise typer.Exit(0)
    for row in rows:
        if row["valid"]:
            prov = row["provenance"]
            typer.echo(f"{row['name']}\t{row['status']}\t{row['spec']}")
            typer.echo(f"  probe: {row['probe']}")
            typer.echo(f"  provenance: run={prov['run_id']} "
                       f"session={prov['session_id'] or '-'} "
                       f"taint_free={prov['taint_free']}")
        else:
            typer.echo(f"{row['name']}\tinvalid\t{row['invalid_reason']}")
    raise typer.Exit(0)
