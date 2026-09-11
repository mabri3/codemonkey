"""Conformance suite: drive the RELEASED BINARY using only build/contract.md.

A second, independent process (no repo imports, no repo knowledge beyond
the contract) checks the binary behaves as documented. Offline probes run
anywhere; live probes (end-to-end exec) pass where an endpoint is reachable
and report BLOCKED otherwise — never green, never silent.

Envelope rule (contract §2): every event carries intelligible `v`; unknown
or missing `v` FAILS the suite. 102F1: the gate is applied to a stream the
BINARY produced (`envelope_probe`), not only to dicts written here — the
C102 shipping version checked hand-built literals, so deleting
`events.stamp` left the suite 7/7 green.
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

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
    # 102F2: stdin=DEVNULL. `exec` with no prompt READS STDIN, so with an
    # open stdin (a pipe, a CI runner, a terminal) the exec-no-prompt probe
    # blocks until the timeout instead of exiting 2 — the suite's verdict
    # depended on the parent's stdin, not on the binary.
    return subprocess.run(
        ["uv", "run", "--project", str(REPO), "codemonkey", *args],
        cwd=cwd or str(REPO), capture_output=True, text=True,
        stdin=subprocess.DEVNULL, timeout=timeout)


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


def envelope_probe(workdir: Path) -> dict:
    """102F1: validate a REAL event stream from the binary, offline.

    The C102 suite as shipped asserted the envelope only against dicts and
    strings written by hand in this file — so a binary with `events.stamp`
    deleted emitted `v`-less events and the suite stayed 7/7 green. The
    break-control could not detect the break it existed to control for.

    No endpoint is needed to observe the envelope: an unreachable endpoint
    still drives `thread.started` / `turn.started` / `error` through the
    exec funnel, and contract §2 binds every one of them. That is the
    control. What is genuinely endpoint-gated is the SUCCESS-path event
    set (`item.*`, `turn.completed` usage) — `live_probe`, and only that,
    reports BLOCKED.
    """
    plain = workdir / "envelope"
    plain.mkdir(exist_ok=True)
    proc = run_binary("exec", "--json", "--skip-git-repo-check",
                      "Reply with the single word: ok", cwd=str(plain))
    if proc.returncode == 2 and not proc.stdout.strip():
        # §1: usage/config error — no provider on this machine at all.
        return {"probe": "envelope", "ok": False, "status": "BLOCKED",
                "reason": f"exit 2 before any event: {proc.stderr[-300:]}"}
    if not proc.stdout.strip():
        raise ConformanceFailure(
            f"[envelope] exit {proc.returncode} with an empty event stream; "
            f"contract §3 says --json stdout carries the JSONL stream: "
            f"{proc.stderr[-300:]}")
    events = check_stream(proc.stdout)
    return {"probe": "envelope", "exit": proc.returncode, "ok": True,
            "status": "PASS", "events": len(events)}


def offline_probes(workdir: Path) -> list[dict]:
    """Probes needing no model endpoint (contract §1 exit codes, §2
    envelope on a real stream)."""
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
        envelope_probe(workdir),
    ]
    return results


def live_probe(workdir: Path) -> dict:
    """End-to-end exec --json on the binary: the SUCCESS-path event set.

    102F1: the envelope itself is checked offline by `envelope_probe`.
    What needs a reachable endpoint is a run that actually completes —
    `item.*` (the public projection; raw `tool.*` is internal by §2) and a
    `turn.completed` carrying usage. Only that is BLOCKED
    when the endpoint is down.
    """
    proc = run_binary("exec", "--json", "--skip-git-repo-check",
                      "Reply with the single word: ok", cwd=str(workdir))
    if proc.returncode != 0:
        # 102F1: in --json mode stderr is empty by contract §3, so a
        # BLOCKED reason built from stderr alone read "exit 1: ". Take the
        # reason from the error event the run actually emitted.
        detail = proc.stderr.strip()
        if not detail:
            for line in reversed(proc.stdout.splitlines()):
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("type") == "error":
                    detail = str(ev.get("message", ""))
                    break
        return {"probe": "live-exec", "status": "BLOCKED",
                "reason": f"exit {proc.returncode}: "
                          f"{detail[-300:] or 'no error event emitted'}"}
    try:
        events = check_stream(proc.stdout)
    except ConformanceFailure as exc:
        raise ConformanceFailure(f"[live-exec] bad envelope: {exc}") from exc
    return {"probe": "live-exec", "status": "PASS",
            "events": len(events)}


# 102F7: contract §2 ON-THE-WIRE enumeration + INTERNAL set. The coverage
# probe FAILS on any wire type no binary-produced stream yields, and on any
# raw tool.* on the wire. 102F6 found plan.* missing by asserting one
# documented type; it found only that one because it asserted only that
# one. Enumerate, don't sample.
CONTRACT = REPO / "build" / "contract.md"
WIRE_BEGIN = "<!-- WIRE-TYPES:BEGIN -->"
WIRE_END = "<!-- WIRE-TYPES:END -->"
INTERNAL_BEGIN = "<!-- INTERNAL-TYPES:BEGIN -->"
INTERNAL_END = "<!-- INTERNAL-TYPES:END -->"
_TYPE_TOKEN = re.compile(r"`([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)?)`")
# The optional dotted part is REQUIRED to be optional: `error`, `notice` and
# `stuck` are type names without a namespace. The first version of this regex
# demanded a dot and silently parsed 15 of §2's 18 wire types — caught by the
# count pin and by the both-directions set check, which is exactly why both
# exist. INVARIANT: a marked region contains TYPE NAMES ONLY (plus each name's
# payload notes in braces); a stray backticked word there would be reported by
# name as "documented but never produced", and would change the pinned count.
# Floor for the parse. A regex that matches nothing must not read as "all
# covered" — that is this cycle's own defect one level down. It is a FLOOR and
# not an exact pin on purpose: removing a type from §2 is a legitimate (if
# major) edit, and an exact pin here would forbid it. The exact counts are
# pinned in tests/test_conformance.py, where a change is visible and deliberate.
MIN_WIRE_TYPES, MIN_INTERNAL_TYPES = 8, 2


def _marked_region(text: str, begin: str, end: str) -> str:
    i = text.find(begin)
    j = text.find(end, i + 1) if i >= 0 else -1
    if i < 0 or j < 0:
        raise ConformanceFailure(
            f"[contract] marker pair {begin!r} … {end!r} not found in "
            f"build/contract.md — §2 is the source of truth and this parser "
            f"refuses to degrade to an empty list")
    return text[i + len(begin):j]


def parse_contract_types(path=None) -> tuple[frozenset, frozenset]:
    """The §2 wire and internal type sets, read OUT OF the document (102F8).

    These used to be hand-maintained constants here — a copy of the contract
    that no edit to the contract could affect. §2 is binding (3bdb346), so
    the document is the source and the code follows it.
    """
    text = (path or CONTRACT).read_text()
    wire = frozenset(
        _TYPE_TOKEN.findall(_marked_region(text, WIRE_BEGIN, WIRE_END)))
    internal = frozenset(
        _TYPE_TOKEN.findall(_marked_region(text, INTERNAL_BEGIN, INTERNAL_END)))
    if len(wire) < MIN_WIRE_TYPES or len(internal) < MIN_INTERNAL_TYPES:
        raise ConformanceFailure(
            f"[contract] the §2 parse produced wire={len(wire)} "
            f"internal={len(internal)} types, below the floor "
            f"({MIN_WIRE_TYPES}/{MIN_INTERNAL_TYPES}) — the markers or the list "
            f"format changed. An empty parse must never read as 'all covered'.")
    both = wire & internal
    if both:
        raise ConformanceFailure(
            f"[contract] §2 lists types as BOTH wire and internal: {sorted(both)}")
    return wire, internal

# 102F10/103: the exit code each stub run produced — the §1 control for a code
# that can only be observed on a run (4 = declared-budget breach).
_LAST_EXIT: dict[str, int] = {}


def _tool_call(name, args) -> str:
    return "TOOL_CALL: " + json.dumps({"name": name, "arguments": args})


def _stub_run(workdir: Path, name: str, turns: list, cli_args: list,
              home: Path, env_extra: Optional[dict] = None) -> list[dict]:
    """One stub-driven binary run; returns its validated event stream."""
    import httpx

    workdir.mkdir(parents=True, exist_ok=True)
    script = workdir / f"{name}.turns.json"
    script.write_text(json.dumps({"turns": turns}))
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen(
        [sys.executable, str(REPO / "build" / "stub_provider.py"),
         str(port), str(script)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                if httpx.get(f"http://127.0.0.1:{port}/v1/models",
                             timeout=2).status_code == 200:
                    break
            except Exception:
                time.sleep(0.2)
        else:
            raise ConformanceFailure(f"[{name}] stub never came up")
        env = dict(os.environ,
                   CODEMONKEY_BASE_URL=f"http://127.0.0.1:{port}/v1",
                   CODEMONKEY_TOOL_PROTOCOL="prompt",
                   CODEMONKEY_API_KEY="dummy",
                   HOME=str(home))
        env.update(env_extra or {})
        out = subprocess.run(
            ["uv", "run", "--project", str(REPO), "codemonkey", "exec",
             "--json", "--skip-git-repo-check", *cli_args],
            cwd=str(workdir), capture_output=True, text=True, timeout=300,
            stdin=subprocess.DEVNULL, env=env)
        if not out.stdout.strip():
            raise ConformanceFailure(
                f"[{name}] exit {out.returncode} with empty stream: "
                f"{out.stderr[-300:]}")
        _LAST_EXIT[name] = out.returncode
        return check_stream(out.stdout)
    finally:
        proc.terminate()
        proc.wait(timeout=15)


def type_coverage(workdir: Path) -> dict:
    """Six stub-driven binary runs; union their wire types; compare.

    A verify pass-with-retry (verify.*, notice, repro.verdict), an atomic
    gave-up (plan.started/rolled_back, failure_report.gave_up/consulted,
    stuck), a successful atomic run (plan.completed), a max-turns burn
    (error), an alternating-failure burn (failure_report.budget_exhausted),
    and a declared-budget halt (budget.exhausted, loop44 C103).
    """
    home = workdir / "home"
    home.mkdir(exist_ok=True)
    runs = {
        # A: write data (verify fails, marker absent) → write marker
        # (verify passes) → final. Covers verify.*, notice, repro.verdict.
        "verify": (
            [_tool_call("write_file", {"path": "data.txt", "content": "d"}),
             _tool_call("write_file", {"path": "marker", "content": "m"}),
             "done"],
            ["--verify-command", "test -f marker", "do the verify task"]),
        # B: charter shape — writes land, then the same failing call until
        # policy gives up. Covers plan.started/rolled_back, gave_up,
        # consulted, stuck.
        "gaveup": (
            [_tool_call("write_file", {"path": "a.txt", "content": "a"}),
             _tool_call("write_file", {"path": "b.txt", "content": "b"}),
             _tool_call("shell", {"command": "exit 1"})],
            ["--atomic-plan", "--sandbox", "danger-full-access",
             "apply the planned edits"]),
        # E: successful atomic run — the plan lands whole. Covers
        # plan.completed (gave-up yields rolled_back instead; without this
        # run, plan.completed is documented-but-unproducible — found by
        # this probe on its first run).
        "atomicok": (
            [_tool_call("write_file", {"path": "ok.txt", "content": "ok"}),
             "done"],
            ["--atomic-plan", "write one file"]),
        # C: a call every turn, never a final answer. Covers error.
        "maxturns": (
            [_tool_call("shell", {"command": "echo hi"})],
            ["--sandbox", "danger-full-access", "--max-turns", "2",
             "keep going"]),
        # D: rotating failures — never the same pair ×3 (no advisory, no
        # gave_up), but the RECOVERY budget burns. Covers
        # failure_report.budget_exhausted (loop 39; distinct from the next).
        "budget": (
            [_tool_call("shell", {"command": "exit 1"}),
             _tool_call("write_file", {"content": "no-path"}),
             _tool_call("read_file", {"path": "no-such-file.txt"})],
            ["--sandbox", "danger-full-access", "--max-turns", "16",
             "keep trying"], None),
        # F: a DECLARED budget (loop44 C103). One turn allowed, two taken →
        # the run halts at its own declared boundary. Covers budget.exhausted
        # and exit code 4. Without this run the type is documented-but-
        # unproducible — the 102F7 question, asked again on purpose.
        "budgetlimit": (
            [_tool_call("write_file", {"path": "a.txt", "content": "a"}),
             _tool_call("write_file", {"path": "b.txt", "content": "b"}),
             "done"],
            ["--sandbox", "danger-full-access", "write two files"],
            {"CODEMONKEY_BUDGET_TURNS": "1"}),
    }
    union: set = set()
    per_run: dict = {}
    events_by_run: dict = {}
    for name, spec in runs.items():
        turns, args = spec[0], spec[1]
        env_extra = spec[2] if len(spec) > 2 else None
        # The stub repeats its LAST turn; multi-turn scripts are explicit
        # lists. Runs C/D need one entry per turn they must survive.
        if name == "maxturns":
            turns = turns * 3
        if name == "budget":
            turns = turns * 6
        events = _stub_run(workdir / name, name, turns, args, home, env_extra)
        types = {e.get("type", "") for e in events}
        per_run[name] = sorted(types)
        events_by_run[name] = events
        union |= types

    # 102F8: §2 is the source of truth, parsed out of the document itself.
    wire_types, internal_types = parse_contract_types()

    # envelope validator already pinned v on every event (check_stream).
    # SET EQUALITY, BOTH DIRECTIONS. Documented-but-unproducible is the
    # direction 102F7 added; produced-but-undocumented is the one that was
    # missing entirely, and it is how a stream starts emitting something the
    # binding contract does not describe.
    missing = sorted(t for t in wire_types if t not in union)
    undocumented = sorted(t for t in union
                          if t not in wire_types and t not in internal_types)
    leaked = sorted(t for t in internal_types if t in union)
    if missing:
        raise ConformanceFailure(
            f"[coverage] documented §2 types never produced: {missing} "
            f"(per-run: {per_run})")
    if undocumented:
        raise ConformanceFailure(
            f"[coverage] types on the wire that §2 documents NOWHERE: "
            f"{undocumented} — either document them as wire types (with a run "
            f"that produces them) or stop emitting them (per-run: {per_run})")
    if leaked:
        raise ConformanceFailure(
            f"[coverage] INTERNAL types on the wire: {leaked}")

    # 102F8: the two budget events must be distinguishable ON THE WIRE, not
    # only in the disambiguation table. `failure_report.budget_exhausted` is
    # the recovery report ({report}); `budget.exhausted` is the declared-budget
    # halt ({field}). A payload that fits both would make the pair confusable
    # in exactly the way the table exists to prevent.
    _rec = [e for e in events_by_run.get("budget", [])
            if e.get("type") == "failure_report.budget_exhausted"]
    _dec = [e for e in events_by_run.get("budgetlimit", [])
            if e.get("type") == "budget.exhausted"]
    if not _rec or not _dec:
        raise ConformanceFailure(
            f"[coverage] the budget pair is not both observable: recovery="
            f"{len(_rec)} declared={len(_dec)} — the disambiguation in §2 "
            f"describes events no run produces")
    if any("field" in e for e in _rec) or any("report" in e for e in _dec) \
            or not any("report" in e for e in _rec) \
            or not any("field" in e for e in _dec):
        raise ConformanceFailure(
            f"[coverage] the two budget events are not disjoint on the wire: "
            f"recovery keys={sorted(k for k in _rec[0])}, declared "
            f"keys={sorted(k for k in _dec[0])}")

    # loop44 C103: contract §1's code 4 ("budget breach") is documented BEFORE
    # its implementation; this is the control that makes the row a claim.
    got = _LAST_EXIT.get("budgetlimit")
    if got != 4:
        raise ConformanceFailure(
            f"[coverage] contract §1 code 4 (budget breach) not observed: the "
            f"declared-budget run exited {got!r}, expected 4")
    return {"probe": "type-coverage", "ok": True,
            "runs": {k: len(v) for k, v in per_run.items()},
            "exit_codes": dict(_LAST_EXIT),
            "documented": {"wire": len(wire_types),
                           "internal": len(internal_types)},
            "covered": len(union & wire_types)}


def main() -> int:
    import tempfile

    with tempfile.TemporaryDirectory(prefix="cm-conform-") as td:
        workdir = Path(td)
        try:
            results = offline_probes(workdir)
            for r in results:
                if r.get("status") == "BLOCKED":
                    print(f"BLOCKED {r['probe']}: {r['reason']}")
                else:
                    print(f"PASS {r['probe']} (exit {r['exit']})")
            cov = type_coverage(workdir)
            print(f"PASS type-coverage ({cov['covered']} §2 types "
                  f"across {cov['runs']})")
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
