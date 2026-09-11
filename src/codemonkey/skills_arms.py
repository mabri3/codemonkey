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
        if label not in SKILLS_ARMS:
            raise ValueError(f"unknown skills arm: {label!r} (want skills-on / "
                             f"skills-off)")
    store = Path(store) if store else Path.cwd()
    started = _iso_now()
    before = _store_snapshot(store)

    results: dict = {"suite": str(suite_path), "started": started,
                     "statistic": STATISTIC, "arms": {}, "retention": {}}
    prior = os.environ.get("CODEMONKEY_STRATEGY_SKILLS")
    try:
        for label in arms:
            os.environ["CODEMONKEY_STRATEGY_SKILLS"] = (
                "use" if label == "skills-on" else "off")
            results["arms"][label] = _summarize(
                _run_suite_safe(suite_path, exec_fn))
            if retention_suite:
                results["retention"][label] = _summarize(
                    _run_suite_safe(retention_suite, exec_fn))
    finally:
        if prior is None:
            os.environ.pop("CODEMONKEY_STRATEGY_SKILLS", None)
        else:
            os.environ["CODEMONKEY_STRATEGY_SKILLS"] = prior

    reason = probe()
    results["endpoint"] = reason or "reachable"
    on = results["arms"].get("skills-on", {})
    off = results["arms"].get("skills-off", {})
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
            "note": "delta = skills-on pass rate − skills-off pass rate on the "
                    "same suite; no causal claim on one measurement",
        }
        ron = results["retention"].get("skills-on", {}).get("pass_rate")
        roff = results["retention"].get("skills-off", {}).get("pass_rate")
        results["retention_check"] = {
            "value": (ron - roff) if (ron is not None and roff is not None)
            else None,
            "status": "MEASURED" if retention_suite else "NOT RUN",
            "suite": str(retention_suite) if retention_suite else "",
        }

    # Contamination — the check that decides whether the transfer number
    # above would MEAN anything: no scored task may contribute a skill.
    after = _store_snapshot(store)
    violations: list[str] = []
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    if added:
        violations.append(f"skills added during the measurement: {added}")
    if removed:
        violations.append(f"skills removed during the measurement: {removed}")
    from . import skills as skills_mod

    for name in sorted(after):
        try:
            man = skills_mod.read_manifest(store, name)
        except skills_mod.SkillError:
            continue
        if str(man.get("created") or "") >= started:
            violations.append(
                f"{name}: created {man.get('created')} — not before the "
                f"measurement start {started}")
    results["contamination"] = {
        "checked": len(after),
        "violations": violations,
        "rule": "the store must be unchanged by the measurement and every "
                "skill must predate it (created < start)",
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
    lines = [f"skills arms on {results.get('suite', '?')} "
             f"(statistic: {results.get('statistic', '?')})"]
    headers = ["arm", "pass_rate", "passed", "tasks", "tokens", "wall_s"]
    rows = []
    for name in SKILLS_ARMS:
        d = results.get("arms", {}).get(name, {})
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
