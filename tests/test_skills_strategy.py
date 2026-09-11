"""loop46 cycle 84 — the `skills` strategy domain: what a run may see, write,
and call.

Discriminating cases, not smoke tests: `off` and `use` must produce the SAME
prompt except for the admitted skill's line (byte-diff); a `use` run calling
`skill_create` must get a tool ERROR and leave the store untouched (not a
write that gets ignored later); a store entry that shadows a built-in must
never load; and an admitted skill must be callable end-to-end through the
real run loop while a read-only run must be refused by the sandbox gate.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from codemonkey import skills
from codemonkey.loop import run_turns
from codemonkey.sandbox import ToolContext

REPO = Path(__file__).resolve().parents[1]


class Turn:
    def __init__(self, content):
        self.content = content
        self.usage = {"total_tokens": 5}
        self.tool_calls = []


class ScriptProv:
    """Replays a scripted reply per call; captures the system prompt."""

    protocol = "openai"

    def __init__(self, script):
        self.script = list(script)
        self.system = None
        self.n = 0

    def chat(self, messages, system=None, **kw):
        if self.system is None:
            self.system = system or ""
        self.n += 1
        if self.n - 1 < len(self.script):
            return Turn(self.script[self.n - 1])
        return Turn("done")


def _ctx(tmp, cfg=None, **extra):
    e = {"config": cfg or {}}
    e.update(extra)
    return ToolContext(workdir=tmp, sandbox="workspace-write", timeout=30,
                       extra=e)


def _admitted_skill(tmp, name="demo_gate", tool_src=None, spec="says hello"):
    skills.write_manifest(tmp, {
        "name": name, "spec": spec,
        "params": {"type": "object", "properties": {}},
        "probe": "echo ok",
        "provenance": {"run_id": "r0", "session_id": "s0", "taint_free": True},
        "status": "quarantined",
    }, tool_src=tool_src or "def run(args, ctx):\n    return {'ok': True, 'output': 'skill-ran'}\n")
    skills.set_status(tmp, name, "admitted", reason="test setup")


def test_off_and_use_prompts_differ_only_by_the_skill_line(tmp_path):
    _admitted_skill(tmp_path)
    prov_off = ScriptProv(["hello"])
    run_turns(prov_off, "hi", _ctx(tmp_path, {"strategies": {"skills": "off"}}),
              tool_protocol="prompt", memory_enabled=False)
    prov_use = ScriptProv(["hello"])
    run_turns(prov_use, "hi", _ctx(tmp_path, {"strategies": {"skills": "use"}}),
              tool_protocol="prompt", memory_enabled=False)
    assert prov_off.system and prov_use.system
    assert "demo_gate" not in prov_off.system
    use_lines = prov_use.system.splitlines()
    off_lines = prov_off.system.splitlines()
    skill_lines = [ln for ln in use_lines if "demo_gate" in ln]
    assert len(skill_lines) == 1  # exactly the one advertised skill line
    # byte-diff: the use prompt is the off prompt PLUS exactly that line
    assert set(use_lines) - set(off_lines) == set(skill_lines)


def test_config_shows_skills_off_by_default():
    r = subprocess.run([sys.executable, "-m", "codemonkey.cli", "config"],
                       capture_output=True, text=True, cwd=str(REPO))
    assert r.returncode == 0, r.stderr
    # YAML quotes the string because bare `off` parses as a boolean
    assert "skills: 'off'" in r.stdout


def test_unknown_skills_strategy_is_exit_2_listing_valid_names():
    import os

    env = os.environ.copy()
    env["CODEMONKEY_STRATEGY_SKILLS"] = "bogus"
    r = subprocess.run([sys.executable, "-m", "codemonkey.cli", "config"],
                       capture_output=True, text=True, cwd=str(REPO), env=env)
    assert r.returncode == 2
    assert "Valid skills strategies: off, use, learn" in (r.stdout + r.stderr)


def test_skill_create_under_use_is_a_tool_error_not_a_write(tmp_path):
    from codemonkey.tools import dispatch

    r = dispatch("skill_create", {
        "name": "demo_use", "spec": "x", "probe": "true",
    }, _ctx(tmp_path, {"strategies": {"skills": "use"}}))
    assert r.ok is False
    assert "learn" in r.output
    assert skills.list_skills(tmp_path) == []     # nothing was written


def test_builtin_shadow_never_loads(tmp_path):
    # A hand-crafted store entry whose name shadows a built-in: invalid per
    # the manifest validator, invisible to load_admitted, absent from prompts.
    d = tmp_path / skills.STORE_DIR / "shell"
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps({
        "name": "shell", "spec": "shadow",
        "params": {"type": "object", "properties": {}},
        "probe": "true",
        "provenance": {"run_id": "r", "session_id": "", "taint_free": True},
        "status": "admitted"}))
    assert skills.load_admitted(tmp_path) == []
    prov = ScriptProv(["hello"])
    run_turns(prov, "hi", _ctx(tmp_path, {"strategies": {"skills": "use"}}),
              tool_protocol="prompt", memory_enabled=False)
    assert prov.system and "shadow" not in prov.system


def test_learn_run_writes_a_quarantined_skill_with_provenance(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / ".home"))
    call = {"name": "skill_create",
            "arguments": {"name": "demo_new", "spec": "runtime-made",
                          "probe": "echo ok",
                          "tool_src": "def run(args, ctx):\n"
                                      "    return {'ok': True, 'output': 'y'}\n"}}
    prov = ScriptProv(["TOOL_CALL: " + json.dumps(call), "created"])
    events: list = []
    run_turns(prov, "make a helper", _ctx(
                  tmp_path, {"strategies": {"skills": "learn"}},
                  run_id="r-run42", session_id="sess-9"),
              tool_protocol="prompt", max_turns=6, memory_enabled=False,
              on_event=events.append)
    rows = skills.list_skills(tmp_path)
    assert [r["name"] for r in rows] == ["demo_new"]
    assert rows[0]["status"] == "quarantined"          # learned, NOT loaded
    man = skills.read_manifest(tmp_path, "demo_new")
    assert man["provenance"] == {"run_id": "r-run42", "session_id": "sess-9",
                                 "taint_free": False}  # no tracker yet: never claim clean
    assert skills.load_admitted(tmp_path) == []
    assert any(e.get("type") == "tool.completed" and e.get("name") == "skill_create"
               and e.get("ok") is True for e in events)


def test_admitted_skill_runs_through_the_loop_and_readonly_is_denied(tmp_path):
    _admitted_skill(tmp_path, "demo_util",
                    tool_src=("def run(args, ctx):\n"
                              "    return {'ok': True, 'output': 'util-ran:' "
                              "+ str(args.get('msg'))}\n"))
    call = {"name": "demo_util", "arguments": {"msg": "hi"}}
    prov = ScriptProv(["TOOL_CALL: " + json.dumps(call), "used it"])
    events: list = []
    run_turns(prov, "use the tool", _ctx(tmp_path, {"strategies": {"skills": "use"}}),
              tool_protocol="prompt", max_turns=6, memory_enabled=False,
              on_event=events.append)
    assert any(e.get("type") == "tool.completed" and e.get("name") == "demo_util"
               and e.get("ok") is True for e in events), events

    # read-only: the sandbox gate refuses skill execution (they run code)
    prov2 = ScriptProv(["TOOL_CALL: " + json.dumps(call), "not allowed"])
    ctx2 = ToolContext(workdir=tmp_path, sandbox="read-only", timeout=30,
                       extra={"config": {"strategies": {"skills": "use"}}})
    turn = run_turns(prov2, "use the tool", ctx2, tool_protocol="prompt",
                     max_turns=6, memory_enabled=False)
    parts = []
    for m in turn.all_messages:
        if isinstance(m, dict):
            parts.append(str(m.get("content", "")))
        else:
            parts.append(str(getattr(m, "content", "")))
    joined = " ".join(parts)
    assert "sandbox-denied" in joined or "not permitted" in joined.lower(), joined
