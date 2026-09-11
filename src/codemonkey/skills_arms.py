"""Skills arms: library-on vs library-off (loop46, cycle 87) — the R-K half.

R-K says "learned" is a measured word: forward transfer AND a retention check,
or the claim is not made. This module is that measurement's plumbing:

* **Arms.** `skills-on` sets `CODEMONKEY_STRATEGY_SKILLS=use` for the run;
  `skills-off` sets `off`. Both run the same suite through the real exec path.
* **Forward transfer.** The pass-rate delta between the arms on a suite whose
  tasks did not produce the skills.
* **Retention.** The same arms on an EARLIER suite — a gain that vanishes on
  old tasks is not retention.
* **R-H statistic.** The named verdict statistic is the time-uniform
  Hoeffding certificate (`certify.hoeffding_gate`), the same one `certify`
  ships — printed by name so no reader has to guess.
* **Contamination.** The check that makes the transfer claim meaningful:
  the store must be UNCHANGED by the measurement and every skill must
  predate it — no scored task may have contributed a skill.

With no endpoint answering, every live figure reports **BLOCKED** with the
probe's own reason — `None`, never `0` — while the arms, the contamination
check and the report shape still run (offline they are exercised with a
scripted exec function; the CLI prints the BLOCKED shape).
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

STATISTIC = "hoeffding-gate (time-uniform certificate, R-H)"
SKILLS_ARMS = ("skills-on", "skills-off")
# loop47 C112: the arms matrix now covers BOTH learned surfaces — skills
# (loop 46) and the playbook (loop 47) — so loop 50 measures them with one
# harness. Each arm is one env switch; the comparator is always the same
# suite run under the two values.
ARM_ENV = {
    "skills-on": ("CODEMONKEY_STRATEGY_SKILLS", "use"),
    "skills-off": ("CODEMONKEY_STRATEGY_SKILLS", "off"),
    "playbook-on": ("CODEMONKEY_STRATEGY_CONTEXT", "playbook"),
    "playbook-off": ("CODEMONKEY_STRATEGY_CONTEXT", "static"),
}
ALL_ARMS = tuple(ARM_ENV)


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def endpoint_probe() -> str:
    """'' when the configured endpoint answers; else the refusal reason.

    One bounded call through codemonkey's own provider layer (the same probe
    shape the acceptance sweep uses, so it follows configuration instead of a
    literal host)."""
    try:
        from .config import load_config, resolve_api_key
        from .providers import build_provider

        cfg = load_config()
        name = cfg.get("default_provider") or "local"
        pconf = (cfg.get("providers") or {}).get(name) or {}
        prov = build_provider(
            pconf.get("protocol", "openai"), pconf.get("base_url", ""),
            pconf.get("model", ""), api_key=resolve_api_key(cfg, name),
            timeout=10, max_retries=0)
        prov.chat([{"role": "user", "content": "ping"}], max_tokens=1)
        return ""
    except Exception as exc:
        return f"{type(exc).__name__}: {str(exc)[:160]}"


def _summarize(run: dict) -> dict:
    tasks = run.get("tasks", []) or []
    total = len(tasks)
    passed = sum(1 for t in tasks if t.get("ok"))
    return {
        "tasks": total,
        "passed": passed,
        # None on an empty suite — never 0.0, which would claim a measured
        # absence over a zero denominator.
        "pass_rate": (passed / total) if total else None,
        "total_tokens": run.get("total_tokens", 0),
        "wall_seconds": run.get("wall_seconds", 0),
        "error": run.get("error", ""),
    }


def _store_snapshot(store: Path) -> dict:
    from . import skills as skills_mod

    return {r["name"]: r.get("status") for r in skills_mod.list_skills(store)}


def _playbook_snapshot(workdir: Path) -> dict:
    from . import playbook as playbook_mod

    return {e["id"]: e.get("status")
            for e in playbook_mod.list_entries(workdir)}


def _contamination_violations(store: Path, before_skills: dict,
                              before_playbook: dict, started: str) -> list[str]:
    """Both learned stores must be UNCHANGED by the measurement, and every
    entry in them must predate it — on either surface, a scored task that
    contributed an artifact invalidates the number the arms produce."""
    from . import playbook as playbook_mod
    from . import skills as skills_mod

    violations: list[str] = []
    after_skills = _store_snapshot(store)
    added = sorted(set(after_skills) - set(before_skills))
    removed = sorted(set(before_skills) - set(after_skills))
    if added:
        violations.append(f"skills added during the measurement: {added}")
    if removed:
        violations.append(f"skills removed during the measurement: {removed}")
    for name in sorted(after_skills):
        try:
            man = skills_mod.read_manifest(store, name)
        except skills_mod.SkillError:
            continue
        if str(man.get("created") or "") >= started:
            violations.append(
                f"skill {name}: created {man.get('created')} — not before "
                f"the measurement start {started}")
    after_pb = _playbook_snapshot(store)
    added = sorted(set(after_pb) - set(before_playbook))
    removed = sorted(set(before_playbook) - set(after_pb))
    if added:
        violations.append(f"playbook entries added during the measurement: {added}")
    if removed:
        violations.append(f"playbook entries removed during the measurement: {removed}")
    for e in playbook_mod.list_entries(store):
        if str(e.get("first_seen") or "") >= started:
            violations.append(
                f"playbook {e['id']}: first_seen {e.get('first_seen')} — not "
                f"before the measurement start {started}")
    return violations


def _run_suite_safe(suite, exec_fn) -> dict:
    """Run one arm's suite, converting a raised provider error into an
    emptied result — offline, `run_exec` raises the transport error instead
    of returning an exit code, and the BLOCKED shape must survive that (this
    matrix is exactly the thing that has to report it honestly)."""
    from .eval import run_suite

    try:
        return run_suite(Path(suite), exec_fn=exec_fn)
    except Exception as exc:
        return {"tasks": [], "error": f"{type(exc).__name__}: {str(exc)[:200]}"}


def run_skills_matrix(suite_path: Path, *, exec_fn=None,
                      arms: Optional[list] = None,
                      retention_suite: Optional[Path] = None,
                      store: Optional[Path] = None,
                      out_dir: Optional[Path] = None,
                      probe: Optional[Callable[[], str]] = None) -> dict:
    """Run the skills-on/skills-off arms and assemble the R-K report.

    `probe` (injectable for tests) reports endpoint reachability; when it
    returns a reason, forward transfer and retention are BLOCKED with that
    reason — the arms still ran, and the contamination check still holds."""
    if exec_fn is None:
        from .exec import run_exec as exec_fn

    if probe is None:
        probe = endpoint_probe

    arms = list(arms or SKILLS_ARMS)
    for label in arms:
        if label not in ARM_ENV:
            raise ValueError(f"unknown arm: {label!r} "
                             f"(want one of {list(ARM_ENV)})")
    surface = "skills" if all(l.startswith("skills-") for l in arms) \
        else ("playbook" if all(l.startswith("playbook-") for l in arms)
              else "mixed")
    store = Path(store) if store else Path.cwd()
    started = _iso_now()
    before = _store_snapshot(store)
    before_pb = _playbook_snapshot(store)

    results: dict = {"suite": str(suite_path), "started": started,
                     "surface": surface,
                     "statistic": STATISTIC, "arms": {}, "retention": {}}
    env_keys = {"CODEMONKEY_STRATEGY_SKILLS", "CODEMONKEY_STRATEGY_CONTEXT"}
    prior_env = {k: os.environ.get(k) for k in env_keys}
    try:
        for label in arms:
            key, val = ARM_ENV[label]
            os.environ[key] = val
            results["arms"][label] = _summarize(
                _run_suite_safe(suite_path, exec_fn))
            if retention_suite:
                results["retention"][label] = _summarize(
                    _run_suite_safe(retention_suite, exec_fn))
    finally:
        for k, v in prior_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    reason = probe()
    results["endpoint"] = reason or "reachable"
    on = results["arms"].get(arms[0], {}) if arms else {}
    off = results["arms"].get(arms[-1], {}) if len(arms) > 1 else {}
    if reason:
        for field, srcdict in (("forward_transfer", results["arms"]),
                               ("retention_check", results["retention"])):
            results[field] = {
                "value": None, "status": "BLOCKED",
                "reason": f"endpoint unreachable at {started}: {reason} — "
                          f"arms ran, numbers withheld; never 0, never green",
            }
    else:
        on_rate, off_rate = on.get("pass_rate"), off.get("pass_rate")
        results["forward_transfer"] = {
            "value": (on_rate - off_rate)
            if (on_rate is not None and off_rate is not None) else None,
            "status": "MEASURED", "on_pass_rate": on_rate,
            "off_pass_rate": off_rate,
            "note": f"delta = {arms[0]} pass rate − {arms[-1]} pass rate on the "
                    "same suite; no causal claim on one measurement",
        }
        ron = results["retention"].get(arms[0], {}).get("pass_rate")
        roff = results["retention"].get(arms[-1], {}).get("pass_rate")
        results["retention_check"] = {
            "value": (ron - roff) if (ron is not None and roff is not None)
            else None,
            "status": "MEASURED" if retention_suite else "NOT RUN",
            "suite": str(retention_suite) if retention_suite else "",
        }

    # Contamination — the check that decides whether the transfer number
    # above would MEAN anything: no scored task may contribute an artifact
    # to EITHER learned store (skills or playbook).
    violations = _contamination_violations(store, before, before_pb, started)
    results["contamination"] = {
        "checked": len(_store_snapshot(store)),
        "playbook_checked": len(_playbook_snapshot(store)),
        "violations": violations,
        "rule": "both stores must be unchanged by the measurement and every "
                "entry must predate it (created/first_seen < start)",
    }

    if violations:
        results["verdict"] = "CONTAMINATED"
    elif reason:
        results["verdict"] = "BLOCKED"
    else:
        results["verdict"] = "MEASURED"

    if out_dir is not None:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "skills_matrix.json").write_text(
            json.dumps(results, indent=2) + "\n")
    return results


def render_skills_table(results: dict) -> str:
    """Arms, the named statistic, transfer, retention, contamination."""
    surface = results.get("surface", "skills")
    lines = [f"{surface} arms on {results.get('suite', '?')} "
             f"(statistic: {results.get('statistic', '?')})"]
    headers = ["arm", "pass_rate", "passed", "tasks", "tokens", "wall_s"]
    rows = []
    for name in results.get("arms", {}):
        d = results["arms"].get(name, {})
        rate = d.get("pass_rate")
        rows.append([name, ("None" if rate is None else f"{rate:.3f}"),
                     str(d.get("passed", "-")), str(d.get("tasks", "-")),
                     str(d.get("total_tokens", "-")),
                     str(d.get("wall_seconds", "-"))])
    widths = [max(len(h), *(len(r[i]) for r in rows))
              for i, h in enumerate(headers)]
    lines.append("  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
    lines.append("  ".join("-" * w for w in widths))
    for r in rows:
        lines.append("  ".join(c.ljust(widths[i]) for i, c in enumerate(r)))
    ft = results.get("forward_transfer", {})
    rt = results.get("retention_check", {})
    val = ft.get("value")
    lines.append(f"forward transfer ({ft.get('status', '?')}): "
                 + ("BLOCKED — " + str(ft.get("reason", ""))
                    if ft.get("status") == "BLOCKED"
                    else ("None" if val is None else f"{val:+.3f}")))
    val = rt.get("value")
    lines.append(f"retention check  ({rt.get('status', '?')}): "
                 + ("BLOCKED — " + str(rt.get("reason", ""))
                    if rt.get("status") == "BLOCKED"
                    else ("None" if val is None
                          else f"{val:+.3f} on {rt.get('suite', '?')}")))
    c = results.get("contamination", {})
    lines.append(f"contamination: checked {c.get('checked', 0)} · "
                 + ("CLEAN" if not c.get("violations")
                    else "VIOLATIONS: " + "; ".join(c["violations"])))
    lines.append(f"verdict: {results.get('verdict', '?')}")
    return "\n".join(lines)
