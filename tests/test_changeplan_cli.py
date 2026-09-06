"""Cycle 102F6 (F2 LOW): the C97 charter probe, CLI-addressable.

The entry claimed "through `codemonkey exec`" while the tests drove
`run_turns` in-process. Rather than rewording, this test runs the RELEASED
BINARY end-to-end against `build/stub_provider.py` (scripted turns over
real HTTP; zero product changes, no endpoint): writes land, the run gets
stuck, policy gives up, the plan rolls back whole — exit 3, tree
byte-identical, `plan.rolled_back` naming the plan on a versioned stream.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent


def _driver():
    path = REPO / "build" / "conformance.py"
    spec = importlib.util.spec_from_file_location("cm_conformance", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _tool(name, args):
    return "TOOL_CALL: " + json.dumps({"name": name, "arguments": args})


TURNS = [
    _tool("write_file", {"path": "a.txt", "content": "aaa"}),
    _tool("write_file", {"path": "c.txt", "content": "changed"}),
    _tool("write_file", {"path": "b.txt", "content": "bbb"}),
    _tool("shell", {"command": "exit 1"}),  # repeats → stuck → gave_up
]


@pytest.fixture
def stub_server(tmp_path):
    if shutil.which("uv") is None:
        pytest.skip("uv not on PATH")
    script = tmp_path / "turns.json"
    script.write_text(json.dumps({"turns": TURNS}))
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, str(REPO / "build" / "stub_provider.py"),
         str(port), str(script)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        import httpx
    except ImportError:
        proc.terminate()
        pytest.skip("httpx not available")
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/v1/models", timeout=2)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.2)
    else:
        proc.terminate()
        pytest.fail("stub provider never came up")
    yield port
    proc.terminate()
    proc.wait(timeout=15)


def test_charter_probe_through_the_binary(tmp_path, monkeypatch, stub_server):
    if shutil.which("git") is None:
        pytest.skip("git not available")
    if shutil.which("uv") is None:
        pytest.skip("uv not on PATH")
    drv = _driver()
    workdir = tmp_path / "ws"
    workdir.mkdir()
    (workdir / "c.txt").write_text("orig")
    subprocess.run(["git", "init", "-q"], cwd=workdir, check=True)
    subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "pre"], cwd=workdir, check=True)
    env = dict(os.environ,
               CODEMONKEY_BASE_URL=f"http://127.0.0.1:{stub_server}/v1",
               CODEMONKEY_TOOL_PROTOCOL="prompt",
               CODEMONKEY_API_KEY="dummy",
               HOME=str(tmp_path / "home"))
    monkeypatch.setenv("CODEMONKEY_BASE_URL", env["CODEMONKEY_BASE_URL"])
    proc = subprocess.run(
        ["uv", "run", "--project", str(REPO), "codemonkey", "exec",
         "--json", "--atomic-plan", "--sandbox", "danger-full-access",
         "apply the planned edits"],
        cwd=str(workdir), capture_output=True, text=True, timeout=300,
        stdin=subprocess.DEVNULL, env=env)  # 102F2: never inherit stdin
    assert proc.returncode == 3, proc.stderr[-500:]
    assert not (workdir / "a.txt").exists()
    assert not (workdir / "b.txt").exists()
    assert (workdir / "c.txt").read_text() == "orig"
    status = subprocess.run(["git", "status", "--porcelain"], cwd=workdir,
                            capture_output=True, text=True,
                            check=True).stdout
    assert status == "", "tree must be byte-identical to pre-plan state"
    events = drv.check_stream(proc.stdout)
    rolled = [e for e in events if e.get("type") == "plan.rolled_back"]
    assert len(rolled) == 1, "exactly one rollback report on the stream"
    rep = rolled[0]["report"]
    assert rep["plan_id"] and rep["files"] == ["a.txt", "b.txt", "c.txt"]
    assert rolled[0]["v"] == 1
