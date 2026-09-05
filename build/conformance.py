"""Conformance suite: drive the RELEASED BINARY using only build/contract.md.

A second, independent process (no repo imports, no repo knowledge beyond
the contract) checks the binary behaves as documented. Offline probes run
anywhere; live probes (end-to-end exec) pass where an endpoint is reachable
and report BLOCKED otherwise — never green, never silent.

Envelope rule (contract §2): every event carries intelligible `v`; unknown
or missing `v` FAILS the suite. `check_envelope` is the mechanical gate a
deliberate schema break must trip (C102 verify).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
KNOWN_VERSIONS = (1,)


class ConformanceFailure(AssertionError):
    pass


def check_envelope(ev: dict) -> dict:
    """Validate one event against contract §2. Raises on any violation."""
    if not isinstance(ev, dict):
        raise ConformanceFailure(f"event is not an object: {type(ev)}")
    if "v" not in ev:
        raise ConformanceFailure(f"event missing v: {ev.get('type')!r}")
    if ev["v"] not in KNOWN_VERSIONS:
        raise ConformanceFailure(f"unknown envelope v={ev['v']!r} "
                                 f"(known {KNOWN_VERSIONS})")
    if "type" not in ev:
        raise ConformanceFailure("event missing type")
    return ev


def check_stream(text: str) -> list[dict]:
    """Validate a --json event stream line by line."""
    events = []
    for i, line in enumerate(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ConformanceFailure(f"line {i}: not JSON: {exc}") from exc
        events.append(check_envelope(ev))
    if not events:
        raise ConformanceFailure("empty event stream")
    return events


def run_binary(*args, cwd=None, timeout=120) -> subprocess.CompletedProcess:
    """The binary under test, addressed only by its documented CLI."""
    return subprocess.run(
        ["uv", "run", "--project", str(REPO), "codemonkey", *args],
        cwd=cwd or str(REPO), capture_output=True, text=True, timeout=timeout)


def probe(name, args, *, expect_exit, cwd=None,
          must_contain_stderr=()) -> dict:
    """One offline probe: exit code + stderr markers from the contract."""
    proc = run_binary(*args, cwd=cwd)
    if proc.returncode != expect_exit:
        raise ConformanceFailure(
            f"[{name}] exit {proc.returncode}, contract says {expect_exit}: "
            f"{proc.stderr[-400:]}")
    for marker in must_contain_stderr:
        if marker not in proc.stderr:
            raise ConformanceFailure(f"[{name}] stderr lacks {marker!r}")
    return {"probe": name, "exit": proc.returncode, "ok": True}


def offline_probes(workdir: Path) -> list[dict]:
    """Probes needing no model endpoint (contract §1 exit codes)."""
    plain = workdir / "plain"
    plain.mkdir(exist_ok=True)
    results = [
        probe("version", ["--version"], expect_exit=0),
        probe("help", ["--help"], expect_exit=0),
        probe("exec-no-prompt", ["exec", "--skip-git-repo-check"],
              expect_exit=2, cwd=str(plain)),
        probe("exec-outside-git", ["exec", "hi"], expect_exit=2,
              cwd=str(plain)),
        probe("rollback-no-id", ["rollback"], expect_exit=2),
        probe("rollback-unknown", ["rollback", "no-such-plan"],
              expect_exit=1),
        probe("rollback-list", ["rollback", "--list"], expect_exit=0),
    ]
    return results


def live_probe(workdir: Path) -> dict:
    """End-to-end exec --json on the binary; versioned stream or BLOCKED."""
    proc = run_binary("exec", "--json", "--skip-git-repo-check",
                      "Reply with the single word: ok", cwd=str(workdir))
    if proc.returncode != 0:
        return {"probe": "live-exec", "status": "BLOCKED",
                "reason": f"exit {proc.returncode}: "
                          f"{proc.stderr[-300:]}"}
    try:
        events = check_stream(proc.stdout)
    except ConformanceFailure as exc:
        raise ConformanceFailure(f"[live-exec] bad envelope: {exc}") from exc
    return {"probe": "live-exec", "status": "PASS",
            "events": len(events)}


def main() -> int:
    import tempfile

    with tempfile.TemporaryDirectory(prefix="cm-conform-") as td:
        workdir = Path(td)
        try:
            results = offline_probes(workdir)
            for r in results:
                print(f"PASS {r['probe']} (exit {r['exit']})")
            live = live_probe(workdir)
            if live["status"] == "PASS":
                print(f"PASS live-exec ({live['events']} events, "
                      "envelope v1)")
            else:
                print(f"BLOCKED live-exec: {live['reason']}")
            print("conformance: offline green; "
                  f"live {live['status']}")
            return 0
        except ConformanceFailure as exc:
            print(f"FAIL {exc}", file=sys.stderr)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
