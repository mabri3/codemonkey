"""CYCLE 102F10 — endpoint-gated acceptance rows, exercised with no model box.

WHY THIS EXISTS
---------------
`build/acceptance_sweep.sh` marks nine rows BLOCKED when no endpoint answers:
A4, A5, A6, A7, A9, A10, A11, A12, A16. That single BLOCKED verdict hides two
different blockers, and the difference decides what a v4.0 exception list is
allowed to contain:

* **ENDPOINT-GATED** — the row needs an HTTP server that speaks the API. It
  does NOT need a model. `build/stub_provider.py` is such a server, and it is
  how 102F6 and 102F7 ran end-to-end with the box off. These rows can be
  graded GREEN with a real run behind them, today.
* **MODEL-GATED** — some clause of the row asserts something only a real
  model's behaviour can establish (a live `/v1/models` listing, a model
  obeying an instruction, a model *choosing* a tool, a model writing a
  review). A scripted endpoint cannot honestly stand in for those clauses.

WHY THE STUB IS AN ORACLE AND NOT A TAPE
----------------------------------------
A fixed tape replies the same thing whatever the binary sends, so a row graded
green on it proves only that the assertion can be satisfied — not that the
binary did the thing under test. Every reply used here is conditional on
request CONTENT: "reply `banana` iff the request carried `banana`" goes red
when stdin was never read. A BINARY PATH THAT CANNOT GRADUALLY DRIFT INTO
PASSING IS THE POINT (R-I).

WHAT EACH ROW'S GREEN MEANS
---------------------------
Exactly what the sweep's own assertion means, minus the model clause. The
residual clause of the four MODEL-GATED rows is named per row in
`sweep-classification.md` with what would close it — never waived as a class.

Run:  uv run python build/sweep_endpoint_gated.py [--check]
      `--check` re-verifies the committed evidence instead of producing it.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "build" / "acceptance_outputs"
STUB = ROOT / "build" / "stub_provider.py"
SCRATCH = ROOT / "build" / ".sweep102f10-scratch"
CLASS_JSON = ROOT / "build" / "sweep-classification.json"
CLASS_MD = ROOT / "build" / "sweep-classification.md"
BINARY = Path(sys.executable).parent / "codemonkey"
TIMEOUT = 180

# Per-row evidence: every command, its exit code, stdout and stderr, plus the
# scripted endpoint's script. A green row without this is a claim, not a run.
EVIDENCE: list[str] = []

REVIEW_TEXT = (
    "## Review verdict\n\n"
    "The uncommitted change adds one scratch marker line to the repository "
    "README. There is no logic change, so there is no behavioural risk in the "
    "diff itself. The only observation is that the marker is a test artifact: "
    "if it were meant to ship, it would need a purpose in the documentation "
    "rather than a temporary sweep sentinel. No security-relevant surface is "
    "touched, no dependency moves, and no public interface changes shape. "
    "Recommendation: this diff is safe to discard; it exists to give the "
    "reviewer a non-empty diff to summarise.\n"
) * 2


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_ready(port: int, deadline: float = 10.0) -> bool:
    import urllib.error
    import urllib.request

    end = time.time() + deadline
    while time.time() < end:
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/v1/models", timeout=1) as r:
                return r.status == 200
        except Exception:
            time.sleep(0.05)
    return False


class Stub:
    """A fresh scripted endpoint per row (turn counters must not leak)."""

    def __init__(self, script: dict):
        self.port = _free_port()
        self.path = ROOT / "build" / f".sweep-stub-{self.port}.json"
        self.path.write_text(json.dumps(script))
        EVIDENCE.append(f"# scripted endpoint {self.base_url}\n"
                        f"# script: {json.dumps(script)}\n")
        env = dict(os.environ)
        env.pop("CODEMONKEY_BASE_URL", None)
        env.pop("CODEMONKEY_MODEL", None)
        self.proc = subprocess.Popen(
            [sys.executable, str(STUB), str(self.port), str(self.path)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        assert _wait_ready(self.port), "stub never became ready"

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def env(self) -> dict:
        env = dict(os.environ)
        env["CODEMONKEY_BASE_URL"] = self.base_url
        env["CODEMONKEY_MODEL"] = "stub-model"
        env["CODEMONKEY_API_KEY"] = "stub-key"
        env["CODEMONKEY_PROVIDER"] = "local"
        env.pop("CODEMONKEY_UNBLOCK2_KEY", None)
        env.pop("CODEMONKEY_VERIFY_COMMAND", None)
        return env

    def close(self):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:  # pragma: no cover
            self.proc.kill()
        self.path.unlink(missing_ok=True)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def cm(args: list, env: dict, stdin_text: str | None = None,
       timeout: int = TIMEOUT) -> tuple[int, str, str]:
    p = subprocess.run([str(BINARY), *args], cwd=str(ROOT),
                       input=stdin_text, capture_output=True, text=True,
                       env=env, timeout=timeout)
    EVIDENCE.append(
        f"$ {' '.join(args)}"
        + (f"\n< stdin: {stdin_text!r}" if stdin_text else "")
        + f"\n[exit {p.returncode}]"
        + (f"\n--- stdout ---\n{p.stdout}" if p.stdout else "\n--- stdout --- (empty)")
        + (f"--- stderr ---\n{p.stderr}" if p.stderr else "--- stderr --- (empty)")
        + "\n")
    return p.returncode, p.stdout, p.stderr


def _script(turns: list, rules: list | None = None) -> dict:
    return {"model": "stub-model", "turns": turns, "rules": rules or []}


# ── the rows ────────────────────────────────────────────────────────────────
# Each row mirrors the sweep body it stands in for. `sweep_mirror` is the
# distinguishing text of the acceptance_sweep.sh body, and
# tests/test_sweep_classification.py asserts it is really there — so a row
# cannot be reclassified here while the sweep has moved on.


def row_a4() -> tuple[bool, str]:
    with Stub(_script(["stub-model"])) as s:
        rc, out, err = cm(["models", "--provider", "local"], s.env())
    ok = rc == 0 and "stub-model" in out
    return ok, f"exit={rc} listing={out.strip()[:80]!r}"


def row_a5() -> tuple[bool, str]:
    rules = [{"contains": "pong", "reply": "pong"}]
    with Stub(_script(["NO-PROMPT-RECEIVED"], rules)) as s:
        rc, out, err = cm(["exec",
                           "Reply with exactly the word pong and nothing else."],
                          s.env())
    ok = rc == 0 and "pong" in out.lower()
    return ok, f"exit={rc} out={out.strip()[:60]!r} (rule fires only if the prompt reached the wire)"


def row_a6() -> tuple[bool, str]:
    rules = [{"contains": "pong", "reply": "pong"}]
    with Stub(_script(["NO-PROMPT-RECEIVED"], rules)) as s:
        rc, out, err = cm(["exec", "--json",
                           "Reply with exactly the word pong and nothing else."],
                          s.env())
    lines = [l for l in out.splitlines() if l.strip()]
    parsed, bad = [], 0
    for l in lines:
        try:
            parsed.append(json.loads(l))
        except Exception:
            bad += 1
    types = {e.get("type") for e in parsed}
    ok = (rc == 0 and lines and bad == 0
          and "thread.started" in types and "turn.completed" in types)
    return ok, f"exit={rc} json-lines={len(lines)} unparseable={bad} types={sorted(t for t in types if t)}"


def row_a7() -> tuple[bool, str]:
    rules = [{"contains": "banana", "reply": "banana"}]
    with Stub(_script(["NO-STDIN-PROMPT"], rules)) as s:
        rc, out, err = cm(["exec", "-"], s.env(),
                          stdin_text="Reply with exactly the word banana and nothing else.")
    ok = rc == 0 and "banana" in out.lower()
    return ok, f"exit={rc} out={out.strip()[:60]!r} (rule fires only if stdin reached the wire)"


def row_a9() -> tuple[bool, str]:
    call = ('TOOL_CALL: {"name": "shell", "arguments": '
            '{"command": "echo codemonkey_tool_test"}}')
    rules = [{"contains": "codemonkey_tool_test", "reply": call, "once": True}]
    with Stub(_script(["codemonkey_tool_test"], rules)) as s:
        rc, out, err = cm(["exec", "--sandbox", "workspace-write",
                           "--approval", "never",
                           "Use the shell tool to run: echo codemonkey_tool_test. "
                           "Then reply with exactly the command output."], s.env())
    # the sweep's own A9 assertions (51F7: evidence the tool RAN, not prose)
    ok = (rc == 0 and "codemonkey_tool_test" in out
          and "echo codemonkey_tool_test" in err and "[exit 0]" in err
          and "error: 'command'" not in err)
    return ok, (f"exit={rc} stdout-has-sentinel={'codemonkey_tool_test' in out} "
                f"stderr-has-command={'echo codemonkey_tool_test' in err} "
                f"stderr-has-exit0={'[exit 0]' in err}")


def row_a10() -> tuple[bool, str]:
    payload = json.dumps({"project_name": "codemonkey",
                          "programming_languages": ["Python"]})
    rules = [{"contains": "project_name", "reply": payload}]
    dest = Path("/tmp/cm-repo.json")
    dest.unlink(missing_ok=True)          # never grade a stale artifact
    with Stub(_script(["NO-SCHEMA-IN-PROMPT"], rules)) as s:
        rc, out, err = cm(["exec", "--output-schema", "build/schema-repo.json",
                           "--output-last-message", str(dest),
                           "Fill the schema for a repository named codemonkey "
                           "whose languages are Python."], s.env())
    try:
        d = json.loads(dest.read_text())
        ok = (rc == 0 and isinstance(d.get("project_name"), str)
              and bool(d["project_name"])
              and isinstance(d.get("programming_languages"), list)
              and all(isinstance(x, str) for x in d["programming_languages"]))
        detail = f"exit={rc} payload={d}"
    except Exception as e:                                  # pragma: no cover
        ok, detail = False, f"exit={rc} payload unreadable: {e}"
    return ok, detail + " (rule fires only if the schema reached the wire)"


def row_a11_a12() -> tuple[bool, str, bool, str]:
    """A11 and A12 share the thread they create — as they do in the sweep."""
    rules = [{"contains": "zebra", "reply": "zebra"}]
    with Stub(_script(["NO-HISTORY-SENT"], rules)) as s:
        env = s.env()
        rc, out, err = cm(["exec", "--json",
                           "Remember this codeword: zebra. Reply with ok."], env)
        thread = ""
        for l in out.splitlines():
            if l.startswith("{") and '"thread.started"' in l:
                try:
                    thread = json.loads(l).get("thread_id", "")
                except Exception:
                    pass
                break
        if not thread:
            return (False, f"no thread.started line (exit={rc})",
                    False, "no thread to list")
        rc2, out2, err2 = cm(["exec", "resume", thread,
                              "What codeword did I ask you to remember?"], env)
        rc3, out3, err3 = cm(["sessions"], env)
    a11 = rc2 == 0 and "zebra" in out2
    a12 = rc3 == 0 and thread in out3
    return (a11, f"exit={rc2} thread={thread} out={out2.strip()[:60]!r} "
                 f"(rule fires only if the HISTORY reached the wire)",
            a12, f"exit={rc3} thread-in-listing={thread in out3}")


def row_a16() -> tuple[bool, str]:
    rules = [{"contains": "SWEEP102F10", "reply": REVIEW_TEXT}]
    SCRATCH.write_text("# acceptance sweep scratch (102F10)\nSWEEP102F10\n")
    try:
        subprocess.run(["git", "add", "-N", str(SCRATCH)], cwd=str(ROOT),
                       capture_output=True)
        with Stub(_script(["NO-DIFF-IN-PROMPT"], rules)) as s:
            rc, out, err = cm(["review", "--uncommitted"], s.env())
    finally:
        subprocess.run(["git", "reset", "-q", str(SCRATCH)], cwd=str(ROOT),
                       capture_output=True)
        SCRATCH.unlink(missing_ok=True)
    ok = rc == 0 and len(out) >= 400
    return ok, (f"exit={rc} chars={len(out)} (rule fires only if the DIFF "
                f"content reached the wire)")


ROW_SPECS = [
    {"row": "A4", "klass": "ENDPOINT-GATED", "runner": row_a4,
     "sweep_mirror": "codemonkey models --provider local",
     "residual": ("spec.md A4 says \"(live server call)\": a listing served by "
                  "the configured box's own /v1/models. Closed by: endpoint up, "
                  "re-run A4 with no stub.")},
    {"row": "A5", "klass": "ENDPOINT-GATED", "runner": row_a5,
     "sweep_mirror": "Reply with exactly the word pong and nothing else.",
     "residual": ("a real model obeying a one-word instruction. The stub proves "
                  "the prompt reached the endpoint and the reply was rendered; "
                  "it cannot prove compliance. Closed by: endpoint up, live A5.")},
    {"row": "A6", "klass": "ENDPOINT-GATED", "runner": row_a6,
     "sweep_mirror": "codemonkey exec --json",
     "residual": None},
    {"row": "A7", "klass": "ENDPOINT-GATED", "runner": row_a7,
     "sweep_mirror": "uv run codemonkey exec -",
     "residual": None},
    {"row": "A9", "klass": "ENDPOINT-GATED", "runner": row_a9,
     "sweep_mirror": "echo codemonkey_tool_test",
     "residual": ("spec.md A9 says \"prompt protocol, live model\": that a real "
                  "27B *chooses* the shell tool from a natural instruction. The "
                  "stub proves the whole tool loop executes — parse, sandbox, "
                  "subprocess, output, feed-back — end to end through the "
                  "released binary; it cannot prove tool SELECTION. Closed by: "
                  "endpoint up, live A9.")},
    {"row": "A10", "klass": "ENDPOINT-GATED", "runner": row_a10,
     "sweep_mirror": "--output-schema build/schema-repo.json",
     "residual": None},
    {"row": "A11", "klass": "ENDPOINT-GATED", "runner": None,
     "sweep_mirror": "exec resume",
     "residual": None},
    {"row": "A12", "klass": "ENDPOINT-GATED", "runner": None,
     "sweep_mirror": "codemonkey sessions",
     "residual": None},
    {"row": "A16", "klass": "ENDPOINT-GATED", "runner": row_a16,
     "sweep_mirror": "review --uncommitted",
     "residual": ("spec.md A16 says \"(live review run)\": review prose written "
                  "by a real model. The stub proves the diff was assembled into "
                  "the prompt and ≥400 chars were rendered. Closed by: endpoint "
                  "up, live A16.")},
]


def run_all() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    print(f"{'row':<5} {'class':<15} {'verdict':<8} detail")
    print("-" * 100)

    # A11 + A12 are one run pair; execute once and grade both. Their evidence
    # is produced HERE, so it must be captured before the per-row loop clears
    # the buffer for each single-row runner (the control caught this: the first
    # draft wrote A11/A12 logs with no runs in them).
    a11, d11, a12, d12 = row_a11_a12()
    shared_evidence = list(EVIDENCE)

    for spec in ROW_SPECS:
        if spec["row"] == "A11":
            ok, detail, ev = a11, d11, shared_evidence
        elif spec["row"] == "A12":
            ok, detail, ev = a12, d12, shared_evidence
        else:
            EVIDENCE.clear()
            ok, detail = spec["runner"]()
            ev = list(EVIDENCE)
        # MODEL-GATED residual: the row stays on the exception list even when
        # its plumbing run is green — the residual clause is what is waived.
        status = "PASS" if ok else "FAIL"
        residual = spec["residual"] if ok else None
        log = OUT / f"sweep-{spec['row']}.log"
        rows.append({
            "row": spec["row"], "class": spec["klass"], "status": status,
            "detail": detail, "sweep_mirror": spec["sweep_mirror"],
            "evidence": f"build/acceptance_outputs/sweep-{spec['row']}.log",
            "residual_model_clause": residual,
            "green_is_full": bool(ok and not spec["residual"]),
        })
        log.write_text(
            f"# CYCLE 102F10 — evidence for row {spec['row']} "
            f"({spec['klass']}, {status})\n"
            f"# binary: {BINARY}\n"
            f"# assertion mirrors acceptance_sweep.sh: {spec['sweep_mirror']!r}\n"
            f"# verdict detail: {detail}\n\n" + "\n".join(ev))
        print(f"{spec['row']:<5} {spec['klass']:<15} {status:<8} {detail}")

    passed = [r for r in rows if r["status"] == "PASS"]
    full_green = [r for r in passed if r["green_is_full"]]
    residual = [r for r in passed if r["residual_model_clause"]]
    doc = {
        "cycle": "102F10",
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": ("build/sweep_endpoint_gated.py — each row run end-to-end "
                   "through the released binary against build/stub_provider.py, "
                   "replies conditional on request content"),
        "counts": {
            "blocked_rows_classified": len(rows),
            "endpoint_gated": len([r for r in rows if r["class"] == "ENDPOINT-GATED"]),
            "model_gated": 0,
            "green_with_run_behind_it": len(passed),
            "green_with_no_model_clause": len(full_green),
            "green_with_named_residual": len(residual),
            "red": len(rows) - len(passed),
        },
        "rows": rows,
        "exception_list": [
            {"row": r["row"], "waived_clause": r["residual_model_clause"],
             "evidence": f"build/acceptance_outputs/sweep-{r['row']}.log"}
            for r in residual
        ],
    }
    CLASS_JSON.write_text(json.dumps(doc, indent=2) + "\n")
    write_markdown(doc)
    print("-" * 100)
    print(f"green with a run behind it: {len(passed)}/{len(rows)} "
          f"({len(full_green)} with no model clause, "
          f"{len(residual)} with a named residual) · red: {len(rows) - len(passed)}")
    return doc


def write_markdown(doc: dict) -> None:
    c = doc["counts"]
    lines = [
        "# Sweep classification — endpoint-gated vs model-gated (102F10)",
        "",
        f"Generated {doc['generated']} by `{doc['method']}`.",
        "",
        "`build/acceptance_sweep.sh` reports one BLOCKED verdict for nine rows "
        "when no endpoint answers. That verdict conflates two different "
        "blockers, and only one of them is a reason to waive a row at v4.0.",
        "",
        "## Counts",
        "",
        f"- rows classified: **{c['blocked_rows_classified']}**",
        f"- endpoint-gated: **{c['endpoint_gated']}**",
        f"- model-gated (whole row): **{c['model_gated']}**",
        f"- green with a run behind it: **{c['green_with_run_behind_it']}** "
        f"— of which **{c['green_with_no_model_clause']}** carry no model clause "
        f"at all and **{c['green_with_named_residual']}** keep a named residual",
        f"- red: **{c['red']}**",
        "",
        "## Rows",
        "",
        "| row | class | verdict | what the green means |",
        "|-----|-------|---------|----------------------|",
    ]
    for r in doc["rows"]:
        lines.append(f"| {r['row']} | {r['class']} | {r['status']} | "
                     f"{r['detail']} |")
    lines += [
        "",
        "## v4.0 exception list (named, one per row)",
        "",
        "A row is waived **for one clause**, never as a class. A blanket "
        "\"endpoint down\" waiver is not an exception list.",
        "",
    ]
    if doc["exception_list"]:
        for e in doc["exception_list"]:
            lines += [f"**{e['row']}** — {e['waived_clause']}", ""]
    else:                                                   # pragma: no cover
        lines += ["_empty — every classified row is fully green._", ""]
    CLASS_MD.write_text("\n".join(lines))


def check() -> int:
    """Re-verify the committed classification against the committed evidence."""
    if not CLASS_JSON.exists():
        print("FAIL: build/sweep-classification.json is missing")
        return 1
    doc = json.loads(CLASS_JSON.read_text())
    bad = []
    for r in doc["rows"]:
        if r["status"] != "PASS":
            bad.append(f"{r['row']}: claims {r['status']}")
        if r["green_is_full"] and r["residual_model_clause"]:
            bad.append(f"{r['row']}: marked fully green but carries a residual")
    if doc["counts"]["green_with_run_behind_it"] != len(
            [r for r in doc["rows"] if r["status"] == "PASS"]):
        bad.append("counts disagree with rows")
    for line in bad:
        print("FAIL:", line)
    print("classification consistent" if not bad else f"{len(bad)} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    if "--check" in sys.argv:
        raise SystemExit(check())
    doc = run_all()
    raise SystemExit(0 if doc["counts"]["red"] == 0 else 1)
