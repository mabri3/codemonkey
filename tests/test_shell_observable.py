"""Cycles 96F1 (shell observability) + 96F2 (path parsing).

96F1: the mutation path must be observable before any rate is claimed.
96F2: distinct edits keyed by path where evidenced.
The R-I probe is end-to-end: a scripted run through `run_turns` with a fake
provider (shell heredoc lands, later edit fails) → journal re-read →
PARTIAL. Plus the negative controls the 91F3 lesson demands.
"""

from __future__ import annotations

import json

from codemonkey.partial import (classify_thread, edit_paths, shell_mutation,
                                shell_targets, summarize)


def _shell_out(cmd, status="ok", ts=1.0):
    return {"type": "outcome", "tool": "shell", "key": "k-" + cmd[:8],
            "status": status, "ts": ts, "cmd": cmd}


# ---------------- 96F1: mutation patterns ----------------

def test_mutating_commands_detected():
    for cmd in ["printf 'hi\\n' > hello.txt",
                "echo x >> log.txt",
                "cat <<EOF > f.txt\nhi\nEOF\n",
                "sed -i 's/a/b/' f.txt",
                "sed --in-place 's/a/b/' f.txt",
                "perl -i -pe 's/a/b/' f.txt",
                "echo hi | tee out.txt",
                "git apply fix.patch",
                "patch -p1 < fix.diff",
                "mv a.txt b.txt",
                "rm dead.txt",
                "git checkout -- f.txt"]:
        mut, pname = shell_mutation(cmd)
        assert mut, f"missed mutating command: {cmd}"
        assert pname, "pattern must be named for audit"


def test_non_mutating_commands_ignored():
    for cmd in ["ls -la",
                "echo hello",
                "cat notes.txt",
                "grep -r foo src | head",
                "make test 2>&1",
                "pytest -q > /dev/null",
                "curl https://example.com | head -c 100",
                "sed 's/a/b/' f.txt",
                "test a -gt b"]:
        mut, _ = shell_mutation(cmd)
        assert not mut, f"false positive on: {cmd}"


def test_redirect_targets_parsed():
    assert shell_targets("printf x > hello.txt") == ["hello.txt"]
    assert shell_targets("a >> l1.txt && b >> l2.txt") == ["l1.txt", "l2.txt"]
    assert shell_targets("cmd 2>&1") == []
    assert shell_targets("cmd > /dev/null") == []


def test_shell_without_cmd_is_dark_never_classified():
    recs = [{"type": "outcome", "tool": "shell", "key": "k1",
             "status": "ok", "ts": 1.0}]
    c = classify_thread(recs)
    assert c["label"] == "NO_EDITS" and c["dark_shell"] == 1


def test_shell_mutation_lands_and_fails_like_edits():
    recs = [_shell_out("printf hi > a.txt", "ok", 1.0),
            _shell_out("git apply missing.patch", "error", 2.0)]
    c = classify_thread(recs)
    assert c["label"] == "PARTIAL"
    assert ("shell-path", "a.txt") in c["landed"]
    assert c["first_landed"] == ("shell-path", "a.txt")


def test_non_mutating_shell_never_arms_partial():
    recs = [_shell_out("ls -la", "error", 1.0)]
    c = classify_thread(recs)
    assert c["label"] == "NO_EDITS"


def test_scope_line_states_dark_count():
    s = summarize({"t": classify_thread(
        [{"type": "outcome", "tool": "shell", "key": "k",
          "status": "ok", "ts": 1.0}])})
    assert s["dark_shell"] == 1
    assert "unobservable" in s["scope"]
    assert "1 shell outcomes predate" in s["scope"]


# ---------------- 96F2: path parsing ----------------

def test_write_output_path_parsed():
    assert edit_paths("write_file", "wrote 106 bytes to /tmp/x/greet.py") == [
        "/tmp/x/greet.py"]


def test_edit_single_forms_parsed():
    assert edit_paths("edit_file",
                      "applied 2 block(s) to src/a.py: ok") == ["src/a.py"]
    assert edit_paths("edit_file",
                      "replaced (exact) in src/b.py") == ["src/b.py"]
    assert edit_paths("edit_file",
                      "replaced 3 occurrence(s) in src/c.py") == ["src/c.py"]
    assert edit_paths("edit_file",
                      "error: edit 0 (src/d.py) block 1/2 failed — nope") == [
        "src/d.py"]


def test_edit_atomic_multi_file_parsed():
    out = ("applied 2 file(s) atomically:\n"
           "src/a.py: applied\nsrc/b.py: applied")
    assert edit_paths("edit_file", out) == ["src/a.py", "src/b.py"]


def test_same_file_double_edit_collapses_to_one_key():
    recs = [
        {"type": "outcome", "tool": "write_file", "key": "k1",
         "status": "ok", "ts": 1.0, "output": "wrote 3 bytes to p.txt"},
        {"type": "outcome", "tool": "edit_file", "key": "k2",
         "status": "ok", "ts": 2.0, "output": "replaced (exact) in p.txt"},
    ]
    c = classify_thread(recs)
    assert c["label"] == "SINGLE", c
    assert c["landed"] == [("path", "p.txt")]


def test_unparseable_output_falls_back_to_hash_key():
    recs = [{"type": "outcome", "tool": "write_file", "key": "abc123",
             "status": "ok", "ts": 1.0, "output": "mystery success"}]
    c = classify_thread(recs)
    assert c["landed"] == [("write_file", "abc123")]


# ---------------- R-I end-to-end: journaled run → PARTIAL ----------------

class _Turn:
    def __init__(self, content):
        self.content = content
        self.reasoning = ""
        self.usage = {"total_tokens": 10}
        self.tool_calls = []


class _ScriptedProv:
    protocol = "prompt"

    def __init__(self, secret):
        self.n = 0
        self.secret = secret

    def chat(self, messages, system=None, **kw):
        self.n += 1
        if self.n == 1:
            # secret-bearing command: must land in the journal redacted
            return _Turn('TOOL_CALL: {"name": "shell", "arguments": '
                         '{"command": "echo %s > hello.txt"}}\\n' % self.secret)
        if self.n == 2:
            return _Turn('TOOL_CALL: {"name": "edit_file", "arguments": '
                         '{"path": "hello.txt", "old_string": "ZZZ-no-match", '
                         '"new_string": "hi"}}\\n')
        return _Turn("done")

    def close(self):
        pass


def test_end_to_end_shell_lands_then_edit_fails_is_partial(
        tmp_path, monkeypatch):
    import tempfile
    from pathlib import Path

    from codemonkey.journal import list_threads, read_thread
    from codemonkey.loop import run_turns
    from codemonkey.sandbox import ToolContext

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    workdir = tmp_path / "ws"
    workdir.mkdir()
    before = set(list_threads())
    secret = "sk-test-secret-needle-0001"
    prov = _ScriptedProv(secret)
    ctx = ToolContext(workdir=workdir, sandbox="danger-full-access")
    run_turns(prov, "make hello then edit it", ctx,
              tool_protocol="prompt", max_turns=5,
              journal_thread="e2e-96f1", journal_run="r1",
              redact_needles=[secret])
    assert (workdir / "hello.txt").exists(), "shell write must really land"
    (after,) = set(list_threads()) - before
    recs = read_thread(after)
    shell_outcomes = [r for r in recs if r.get("type") == "outcome"
                      and r.get("tool") == "shell"]
    assert shell_outcomes and all("cmd" in r for r in shell_outcomes)
    assert all(secret not in r["cmd"] for r in shell_outcomes), \
        "secret-bearing command must be redacted at rest"
    c = classify_thread(recs)
    assert c["label"] == "PARTIAL", c
    assert c["first_landed"] == ("shell-path", "hello.txt")


def test_none_needles_stores_no_cmd(tmp_path, monkeypatch):
    from codemonkey.journal import list_threads, read_thread
    from codemonkey.loop import run_turns
    from codemonkey.sandbox import ToolContext

    home = tmp_path / "home2"
    monkeypatch.setenv("HOME", str(home))
    workdir = tmp_path / "ws2"
    workdir.mkdir()
    before = set(list_threads())

    class _Ls:
        protocol = "prompt"

        def chat(self, messages, system=None, **kw):
            if not hasattr(self, "n"):
                self.n = 0
            self.n += 1
            if self.n == 1:
                return _Turn('TOOL_CALL: {"name": "shell", "arguments": '
                             '{"command": "ls"}}\\n')
            return _Turn("done")

        def close(self):
            pass

    ctx = ToolContext(workdir=workdir, sandbox="danger-full-access")
    run_turns(_Ls(), "list", ctx, tool_protocol="prompt", max_turns=3,
              journal_thread="e2e-96f1-none", journal_run="r1",
              redact_needles=None)
    (after,) = set(list_threads()) - before
    recs = read_thread(after)
    assert [r for r in recs if r.get("type") == "outcome"
            and r.get("tool") == "shell"]
    assert all("cmd" not in r for r in recs), \
        "unknown provenance must store nothing"


def test_cmd_truncated_at_500(tmp_path, monkeypatch):
    from codemonkey.journal import list_threads, read_thread
    from codemonkey.loop import run_turns
    from codemonkey.sandbox import ToolContext

    monkeypatch.setenv("HOME", str(tmp_path / "home3"))
    workdir = tmp_path / "ws3"
    workdir.mkdir()
    before = set(list_threads())

    class _Long:
        protocol = "prompt"

        def chat(self, messages, system=None, **kw):
            if not hasattr(self, "n"):
                self.n = 0
            self.n += 1
            if self.n == 1:
                return _Turn('TOOL_CALL: {"name": "shell", "arguments": '
                             '{"command": "echo ' + "y" * 900 + '"}}\\n')
            return _Turn("done")

        def close(self):
            pass

    ctx = ToolContext(workdir=workdir, sandbox="danger-full-access")
    run_turns(_Long(), "long", ctx, tool_protocol="prompt", max_turns=3,
              journal_thread="e2e-96f1-trunc", journal_run="r1",
              redact_needles=[])
    (after,) = set(list_threads()) - before
    cmds = [r["cmd"] for r in read_thread(after) if "cmd" in r]
    assert cmds and max(len(c) for c in cmds) <= 500
