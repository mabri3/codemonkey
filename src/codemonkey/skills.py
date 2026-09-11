"""Skill artifact format + quarantined store (loop46, cycle 82).

A run that makes the next run cheaper needs somewhere to put what it learned —
and that place must be **quarantined by construction**, because R-J says
nothing the agent writes about itself is trusted until earned, and everything
it writes is revocable by one command.

The store lives at `<workspace>/.codemonkey/skills/<name>/` and holds two
files: `manifest.json` (name, one-line spec, JSON-Schema params, the skill's
own self-probe command, provenance, status, history) and `tool.py` (the
candidate tool body). Two properties are enforced HERE, mechanically:

* **Gitignored by default.** Creating a skill ensures the workspace
  `.gitignore` covers `.codemonkey/skills/`, so a candidate tool body cannot
  ride a commit out of the workspace before it has earned admission.
* **Never loaded unless `admitted`.** `load_admitted()` returns ONLY skills
  whose validated status is exactly `admitted` — quarantine, eviction and
  operator disable all read as "not loaded". Promotion is cycle 83's gate
  (a mechanical self-probe in the sandbox); this module never promotes on its
  own opinion, and this cycle (82) does not load skills into any run at all.

Provenance is mandatory and structured — originating run id, session id, and
whether the producing turn was taint-free — because cycle 85's coarse taint
rule and loop 49's full propagation must be able to refuse contaminated
lineage LATER, after the writing turn is gone. A manifest without provenance
parses as nothing.

Statuses: `quarantined` (the only state a new skill may start in) →
`admitted` (only the C83 gate sets this) → `evicted` (R-A: a later probe
failure) or `disabled` (operator). `set_status` is the MECHANISM for all
four transitions and deliberately enforces none of the gate policy — the
policy lives in the gate that has a probe behind it, not in the store.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

STORE_DIR = ".codemonkey/skills"
STATUSES: tuple[str, ...] = ("quarantined", "admitted", "evicted", "disabled")
REQUIRED_KEYS = ("name", "spec", "params", "probe", "provenance", "status")
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")


class SkillError(ValueError):
    """A manifest or store operation that is refused, with the reason."""


def store_root(workdir: str | Path) -> Path:
    return Path(workdir) / ".codemonkey" / "skills"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_builtin(name: str) -> bool:
    """A skill may never shadow a built-in tool: the registry is the single
    already-policed admission point, and a name collision would make dispatch
    ambiguous exactly where ambiguity is most expensive."""
    try:
        from .tools import SPECS

        return name in SPECS
    except Exception:  # pragma: no cover — registry is import-safe by design
        return False


def validate_manifest(man: Any) -> None:
    """Raise SkillError naming the first problem. Checked on write AND on
    every read that matters, because a hand-edited manifest is the threat
    model, not an edge case."""
    if not isinstance(man, dict):
        raise SkillError("manifest must be a JSON object")
    for key in REQUIRED_KEYS:
        if key not in man:
            raise SkillError(f"manifest is missing required field {key!r}")
    name = man["name"]
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise SkillError(
            f"skill name {name!r} is invalid (lowercase letters, digits, "
            f"underscores; must start with a letter)")
    if is_builtin(name):
        raise SkillError(
            f"skill name {name!r} collides with a built-in tool — built-in "
            f"names always win and a colliding candidate is refused")
    if not isinstance(man["spec"], str) or not man["spec"].strip():
        raise SkillError("spec must be a non-empty one-line description")
    params = man["params"]
    if not isinstance(params, dict) or params.get("type") != "object":
        raise SkillError(
            "params must be a JSON-Schema object (type: object, properties)")
    if not isinstance(params.get("properties"), dict):
        raise SkillError(
            "params.properties must be an object (even empty) — a params "
            "schema without properties describes nothing")
    req = params.get("required")
    if req is not None and (not isinstance(req, list)
                            or not all(isinstance(x, str) for x in req)):
        raise SkillError("params.required must be a list of strings")
    if not isinstance(man["probe"], str) or not man["probe"].strip():
        raise SkillError(
            "probe must be a non-empty command — a skill without a self-probe "
            "can never earn admission")
    prov = man["provenance"]
    if not isinstance(prov, dict):
        raise SkillError("provenance is required and must be an object")
    for key in ("run_id", "session_id", "taint_free"):
        if key not in prov:
            raise SkillError(f"provenance is missing {key!r}")
    if not isinstance(prov["run_id"], str) or not prov["run_id"]:
        raise SkillError("provenance.run_id must be a non-empty string")
    if not isinstance(prov["session_id"], str):
        raise SkillError("provenance.session_id must be a string")
    if not isinstance(prov["taint_free"], bool):
        raise SkillError("provenance.taint_free must be a boolean")
    if man["status"] not in STATUSES:
        raise SkillError(
            f"status {man['status']!r} is not one of {list(STATUSES)}")


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def ensure_ignored(workdir: str | Path) -> Path:
    """The store must not be committable by default. Ensures the workspace
    `.gitignore` carries `.codemonkey/skills/`; idempotent."""
    gi = Path(workdir) / ".gitignore"
    line = STORE_DIR + "/"
    try:
        existing = gi.read_text() if gi.exists() else ""
    except OSError:
        existing = ""
    lines = [ln.strip() for ln in existing.splitlines()]
    if line in lines or ".codemonkey/" in lines or ".codemonkey" in lines:
        return gi
    sep = "" if existing.endswith("\n") or not existing else "\n"
    _atomic_write(gi, existing + sep + line + "\n")
    return gi


def skill_dir(workdir: str | Path, name: str) -> Path:
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise SkillError(f"skill name {name!r} is invalid")
    return store_root(workdir) / name


def read_manifest(workdir: str | Path, name: str) -> dict:
    """Read + validate one manifest. Refuses with the reason when the file is
    missing, unparseable, or invalid."""
    path = skill_dir(workdir, name) / "manifest.json"
    if not path.exists():
        raise SkillError(f"no skill named {name!r} in {store_root(workdir)}")
    try:
        man = json.loads(path.read_text())
    except ValueError as exc:
        raise SkillError(f"{name}: manifest.json is not valid JSON: {exc}") \
            from None
    validate_manifest(man)
    return man


def write_manifest(workdir: str | Path, man: dict,
                   tool_src: Optional[str] = None) -> Path:
    """Validate, ensure the store is ignored, and write the skill atomically.

    A skill that is no longer quarantined is NOT clobberable: replacing the
    tool body of an admitted skill behind the gate's back is exactly the
    attack R-J's ordering (quarantine → gate → admit) exists to stop. Re-run
    this to update a still-quarantined candidate."""
    man = dict(man)
    man.setdefault("status", "quarantined")
    man.setdefault("history", [])
    man.setdefault("created", _now())
    validate_manifest(man)
    d = skill_dir(workdir, man["name"])
    if d.exists():
        try:
            current = read_manifest(workdir, man["name"])
        except SkillError:
            current = None
        if current is not None and current["status"] != "quarantined":
            raise SkillError(
                f"{man['name']}: refusing to overwrite a skill whose status "
                f"is {current['status']!r} (only quarantined candidates are "
                f"replaceable; revoke or evict first)")
    ensure_ignored(workdir)
    d.mkdir(parents=True, exist_ok=True)
    if tool_src is not None:
        _atomic_write(d / "tool.py", tool_src)
    path = d / "manifest.json"
    _atomic_write(path, json.dumps(man, indent=2, sort_keys=True) + "\n")
    return path


def list_skills(workdir: str | Path) -> list[dict]:
    """Every skill in the store, honestly labeled. An invalid manifest is
    surfaced as `status: invalid` with its error — never skipped silently,
    because a store that hides broken candidates cannot be audited.

    No store → `[]` (honest empty; a missing store is not an error)."""
    root = store_root(workdir)
    out: list[dict] = []
    if not root.is_dir():
        return out
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        try:
            man = read_manifest(workdir, d.name)
            out.append({
                "name": man["name"], "status": man["status"],
                "spec": man["spec"], "probe": man["probe"],
                "params": man["params"],
                "provenance": man["provenance"], "valid": True,
                "dir": str(d),
            })
        except SkillError as exc:
            out.append({"name": d.name, "status": "invalid", "spec": "",
                        "invalid_reason": str(exc), "valid": False,
                        "dir": str(d)})
    out.sort(key=lambda r: r["name"])
    return out


def load_admitted(workdir: str | Path) -> list[dict]:
    """The ONLY loader a run may use this era: valid manifests with status
    exactly `admitted`. Everything else — quarantined, evicted, disabled,
    invalid — reads as not loaded. No store → `[]`.

    A library-level disable flag (R-J: `codemonkey skills disable`) reads as
    zero skills WITHOUT deleting any evidence — the manifests and history
    stay on disk; only the load stops."""
    if is_disabled(workdir):
        return []
    return [r for r in list_skills(workdir)
            if r["valid"] and r["status"] == "admitted"]


DISABLED_MARKER = ".disabled"


def is_disabled(workdir: str | Path) -> bool:
    return (store_root(workdir) / DISABLED_MARKER).exists()


def set_disabled(workdir: str | Path, disabled: bool,
                 reason: str = "") -> bool:
    """Turn the whole library off (or back on) for this workspace. The off
    state is a marker file, never a deletion — every manifest, log and
    verdict survives, so `disable` is reversible and auditable. Returns the
    new state."""
    root = store_root(workdir)
    marker = root / DISABLED_MARKER
    if disabled:
        root.mkdir(parents=True, exist_ok=True)
        _atomic_write(marker, json.dumps({"at": _now(), "reason": reason}) + "\n")
    else:
        try:
            marker.unlink()
        except FileNotFoundError:
            pass
    return disabled


def revoke(workdir: str | Path, name: str) -> dict:
    """R-J revocation in one command: the skill is REMOVED (its store
    directory is deleted), which restores prior behavior immediately — the
    next load cannot see it. The removal itself is journaled by the caller
    (`skill.revoked`), so the act is auditable even though the artifact is
    gone. A skill that never existed is refused, not silently ignored."""
    import shutil

    man = read_manifest(workdir, name)  # validates existence (raises SkillError)
    d = skill_dir(workdir, name)
    shutil.rmtree(d)
    return {"name": name, "removed": True, "was": man["status"]}


def set_status(workdir: str | Path, name: str, status: str,
               reason: str = "") -> dict:
    """Move a skill between statuses and journal the move in the manifest's
    own history. Any of the four statuses is accepted — the POLICY (what may
    promote, when, and on what evidence) belongs to the gate cycles that ship
    with probes, not to this mechanism."""
    if status not in STATUSES:
        raise SkillError(f"status {status!r} is not one of {list(STATUSES)}")
    man = read_manifest(workdir, name)
    entry = {"from": man["status"], "to": status, "at": _now(), "reason": reason}
    man["status"] = status
    man.setdefault("history", []).append(entry)
    path = skill_dir(workdir, name) / "manifest.json"
    _atomic_write(path, json.dumps(man, indent=2, sort_keys=True) + "\n")
    return man


# --- the admission gate (cycle 83) ------------------------------------------
#
# Promotion is a MECHANICAL question with one input: the candidate's own
# self-probe, executed through the EXISTING sandbox at the admitting run's
# level (never above it — a level that cannot run shell refuses the probe
# instead of widening), decided by the process exit code alone. A model's
# opinion is never an input: nothing on this path calls a provider. The
# verdict is journaled with the probe's actual output, and an ADMITTED skill
# whose probe later fails is evicted in the same motion (R-A) — an artifact
# that outlives its evidence does not stay loaded.

def skill_thread(workdir: str | Path) -> str:
    """The journal thread for this workspace's skill events — deterministic
    and readable, so \"the journal carries skill.admitted\" is checkable."""
    name = Path(workdir).resolve().name or "workspace"
    return f"skills-{name}"


def _default_level() -> str:
    try:
        from .config import load_config

        return str(load_config().get("sandbox") or "workspace-write")
    except Exception:
        return "workspace-write"


def _excerpt(text: str, n: int = 400) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[:n] + f"… (+{len(text) - n} chars)"


def admit(workdir: str | Path, name: str, *, level: Optional[str] = None,
          timeout: float = 60.0, override: bool = False) -> dict:
    """Run the candidate's self-probe and let the exit code decide.

    Returns `{"name", "ok", "probe_exit", "status", "reason", "output",
    "level", "thread"}`; the same verdict is journaled on the workspace's
    skill thread (`skill.admitted` / `skill.refused` / `skill.evicted`, with
    the exit code and a bounded excerpt of the probe output)."""
    import subprocess

    from . import journal as journal_mod
    from . import sandbox as sandbox_mod

    workdir = Path(workdir)
    level = level or _default_level()
    if level not in sandbox_mod.LEVELS:
        raise SkillError(f"unknown sandbox level {level!r} "
                         f"(valid: {list(sandbox_mod.LEVELS)})")
    man = read_manifest(workdir, name)
    thread = skill_thread(workdir)
    prov = man.get("provenance") or {}
    if prov.get("taint_free") is False and not override:
        # loop49 C119: read-side gate — a manifest with tainted provenance
        # (hand-edited, migrated, or written before the write-side rule) is
        # refused WITHOUT running its probe; the operator override is
        # explicit and journaled.
        try:
            journal_mod.record(thread, "skill.refused", tool="skills",
                               key=name, status="tainted",
                               fields={"reason": "tainted",
                                       "source": str(prov.get("source")
                                                     or "provenance")})
        except Exception:
            pass
        return {"name": name, "ok": False, "probe_exit": None,
                "status": man["status"],
                "reason": "provenance.taint_free is false — a tainted-derived "
                          "skill may not be admitted without --override",
                "output": "", "level": level, "thread": thread}

    def _journal(rtype: str, exit_code: object, output: str) -> None:
        try:
            journal_mod.record(thread, rtype, tool="skills", key=name,
                               status=f"probe_exit:{exit_code}",
                               output=_excerpt(output))
        except Exception:  # journaling is best-effort by contract
            pass

    ctx = sandbox_mod.ToolContext(workdir=workdir, sandbox=level,
                                  timeout=timeout)
    try:
        sandbox_mod.check("shell", ctx)
    except sandbox_mod.SandboxError as exc:
        reason = f"sandbox refuses to run a probe at level {level!r}: {exc}"
        _journal("skill.refused", "sandbox", reason)
        return {"name": name, "ok": False, "probe_exit": None,
                "status": man["status"], "reason": reason, "output": "",
                "level": level, "thread": thread}

    try:
        proc = subprocess.run(["bash", "-lc", man["probe"]], cwd=str(workdir),
                              capture_output=True, text=True, timeout=timeout,
                              stdin=subprocess.DEVNULL)
        code: object = proc.returncode
        combined = f"stdout: {proc.stdout.strip()}\nstderr: {proc.stderr.strip()}"
    except subprocess.TimeoutExpired:
        code = "timeout"
        combined = f"probe exceeded {timeout}s and was killed"
    except OSError as exc:
        code = "spawn-error"
        combined = f"probe could not be started: {exc}"

    if code == 0:
        updated = set_status(workdir, name, "admitted",
                             reason=f"self-probe exit 0 at {level}")
        _journal("skill.admitted", code, combined)
        return {"name": name, "ok": True, "probe_exit": 0,
                "status": updated["status"],
                "reason": f"probe exit 0 at {level} — promoted",
                "output": combined, "level": level, "thread": thread}

    if man["status"] == "admitted":
        updated = set_status(workdir, name, "evicted",
                             reason=f"post-admission probe failed: exit {code}")
        _journal("skill.evicted", code, combined)
        return {"name": name, "ok": False, "probe_exit": code,
                "status": updated["status"],
                "reason": f"probe exit {code} AFTER admission — evicted (R-A)",
                "output": combined, "level": level, "thread": thread}

    _journal("skill.refused", code, combined)
    return {"name": name, "ok": False, "probe_exit": code,
            "status": man["status"],
            "reason": f"probe exit {code} — stays {man['status']}",
            "output": combined, "level": level, "thread": thread}


# --- dispatch: calling an admitted skill (cycle 84) --------------------------
#
# A skill call is gated at least as strictly as `shell` (a skill's body is
# arbitrary code — the gate proves it RUNS, not that it is tame), and the
# skill's tool.py executes in a CHILD process: agent-authored code is never
# imported into this one. The parent checks the gate; the child only runs.

def dispatch(workdir: str | Path, name: str, args: dict, *,
             level: str = "workspace-write", timeout: float = 60.0) -> dict:
    """Call an admitted skill. Returns `{"ok", "output", "error"}`.

    Refused when the skill is not `admitted` (R-J: quarantined/evicted/
    disabled read as not loaded) or when the sandbox level cannot run it."""
    import subprocess
    import sys

    from . import sandbox as sandbox_mod

    workdir = Path(workdir)
    if is_disabled(workdir):
        return {"ok": False, "output": "",
                "error": f"the skill library is disabled for this workspace "
                         f"(codemonkey skills disable) — nothing loads, so "
                         f"nothing is callable"}
    try:
        man = read_manifest(workdir, name)
    except SkillError as exc:
        return {"ok": False, "output": "", "error": str(exc)}
    if man["status"] != "admitted":
        return {"ok": False, "output": "",
                "error": f"skill {name!r} is {man['status']!r} — not callable "
                         f"until admitted (R-J)"}
    ctx = sandbox_mod.ToolContext(workdir=workdir, sandbox=level,
                                  timeout=timeout)
    try:
        sandbox_mod.check("shell", ctx)
    except sandbox_mod.SandboxError as exc:
        return {"ok": False, "output": "",
                "error": f"sandbox-denied: a skill executes code; {exc}"}
    tool_path = skill_dir(workdir, name) / "tool.py"
    if not tool_path.is_file():
        return {"ok": False, "output": "",
                "error": f"{name}: tool.py is missing — the store entry is "
                         f"incomplete"}
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "codemonkey.skill_runner", str(tool_path),
             json.dumps(args or {})],
            cwd=str(workdir), capture_output=True, text=True, timeout=timeout,
            stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": "",
                "error": f"{name}: timed out after {timeout}s"}
    out = (proc.stdout or "").strip()
    payload = None
    if out:
        try:
            payload = json.loads(out.splitlines()[-1])
        except ValueError:
            payload = None
    if proc.returncode != 0 or not isinstance(payload, dict):
        detail = (proc.stderr or "").strip()[-600:] or "no result payload"
        return {"ok": False, "output": out[-600:],
                "error": f"{name}: exit {proc.returncode}; {detail}"}
    err = str(payload.get("error", ""))
    return {"ok": bool(payload.get("ok")), "output": str(payload.get("output", "")),
            "error": err}
