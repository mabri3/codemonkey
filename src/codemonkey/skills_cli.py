"""`codemonkey skills` — the operator surface for the quarantined store.

Cycle 82 ships `list` (honest empty when no store exists — a missing store is
not an error); cycle 83 adds `admit` (the mechanical gate: the candidate's
own self-probe, through the existing sandbox, exit code decides). The
revocation verbs (`show`, `revoke`, `disable`, cycle 86) land beside them.
"""

from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(help="Skill library: quarantined store + admission gate.")


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


@app.command("show")
def show_cmd(
    name: str = typer.Argument(..., help="skill name"),
) -> None:
    """Print one skill's full record — spec, params, probe, provenance
    (including the originating run id), status and its full history."""
    import json as _json

    from . import skills

    try:
        man = skills.read_manifest(Path.cwd(), name)
    except skills.SkillError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from None
    typer.echo(f"{man['name']}  [{man['status']}]")
    typer.echo(f"  spec:    {man['spec']}")
    typer.echo(f"  probe:   {man['probe']}")
    typer.echo(f"  params:  {_json.dumps(man['params'], sort_keys=True)}")
    prov = man["provenance"]
    typer.echo(f"  provenance: run_id={prov['run_id']} "
               f"session_id={prov['session_id'] or '-'} "
               f"taint_free={prov['taint_free']}")
    typer.echo(f"  created: {man.get('created', '?')}")
    for h in man.get("history", []):
        typer.echo(f"  {h['at']}  {h['from']} -> {h['to']}  ({h['reason']})")
    raise typer.Exit(0)


@app.command("revoke")
def revoke_cmd(
    name: str = typer.Argument(..., help="skill name to remove"),
) -> None:
    """R-J revocation in ONE command: delete the skill and restore prior
    behavior — the next load cannot see it. Journaled (`skill.revoked`)."""
    from . import journal, skills

    cwd = Path.cwd()
    try:
        res = skills.revoke(cwd, name)
    except skills.SkillError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from None
    try:
        journal.record(skills.skill_thread(cwd), "skill.revoked",
                       tool="skills", key=name, status=f"was-{res['was']}")
    except Exception:
        pass
    typer.echo(f"{name}: revoked (was {res['was']}) — removed; the next load "
               f"cannot see it")
    raise typer.Exit(0)


@app.command("disable")
def disable_cmd(
    enable: bool = typer.Option(False, "--enable",
                                help="turn the library back on (removes the marker)"),
) -> None:
    """Turn the whole skill library OFF for this workspace — no skills load,
    no skill is callable — WITHOUT deleting evidence (manifests, history and
    verdicts all stay on disk). `--enable` reverses it. Journaled."""
    from . import journal, skills

    cwd = Path.cwd()
    skills.set_disabled(cwd, not enable,
                        reason="operator disable" if not enable else "")
    try:
        journal.record(skills.skill_thread(cwd),
                       "skills.disabled" if not enable else "skills.enabled",
                       tool="skills", key="*",
                       status="disabled" if not enable else "enabled")
    except Exception:
        pass
    state = "DISABLED" if not enable else "ENABLED"
    typer.echo(f"skill library {state} for {cwd} — "
               + ("zero skills load; evidence kept on disk"
                  if not enable else "admitted skills load again"))
    raise typer.Exit(0)


@app.command("admit")
def admit_cmd(
    name: str = typer.Argument(..., help="skill name to run through the gate"),
    sandbox: str = typer.Option(
        "", "--sandbox",
        help="sandbox level the probe runs at (default: effective config; "
             "the gate never runs a probe above it)"),
    timeout: float = typer.Option(60.0, "--timeout",
                                  help="probe timeout, seconds"),
) -> None:
    """Run a candidate's self-probe and promote it on exit 0 only.

    Exit 0 = admitted · 1 = refused or evicted (see the reason) · 2 = usage
    error (unknown skill, invalid manifest, unknown sandbox level)."""
    from . import skills

    try:
        result = skills.admit(Path.cwd(), name,
                              level=(sandbox or None), timeout=timeout)
    except skills.SkillError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from None

    head = f"{result['name']}: {result['status'].upper()}"
    typer.echo(f"{head} — {result['reason']}")
    if result["output"]:
        for line in result["output"].splitlines():
            typer.echo(f"  {line}")
    typer.echo(f"  journal: {result['thread']} "
               f"(probe_exit:{result['probe_exit']})")
    raise typer.Exit(0 if result["ok"] else 1)
