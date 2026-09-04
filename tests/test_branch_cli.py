"""Cycle 80 (loop 38): `codemonkey branch` over git worktrees in .branches/.

R-I entry-point probe: on a scratch git repo, `branch create demo` → exit 0
with .branches/demo on `git worktree list`; `branch diff demo` → exit 0;
`branch remove demo` → exit 0 and gone; outside a git repo → exit 2.
"""

from __future__ import annotations

import subprocess

import pytest
from typer.testing import CliRunner

from codemonkey.branches import branch_diff, branch_list
from codemonkey.cli import app

runner = CliRunner()


def _scratch_repo(path):
    path.mkdir(parents=True, exist_ok=True)

    def git(*args):
        r = subprocess.run(["git", *args], cwd=path, capture_output=True,
                           text=True, timeout=60)
        assert r.returncode == 0, r.stderr
        return r

    git("init", "-b", "main")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit",
        "--allow-empty", "-m", "seed")
    return path


def _worktrees(path):
    r = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=path,
                       capture_output=True, text=True, timeout=60)
    return r.stdout


# ---------------- R-I: CLI on a scratch repo ----------------

def test_create_list_diff_remove_cycle(tmp_path, monkeypatch):
    repo = _scratch_repo(tmp_path / "repo")
    monkeypatch.chdir(repo)

    r = runner.invoke(app, ["branch", "create", "demo"])
    assert r.exit_code == 0, r.output
    assert (repo / ".branches" / "demo").is_dir()
    assert ".branches/demo" in _worktrees(repo)
    assert "demo" in branch_list(repo)

    r = runner.invoke(app, ["branch", "diff", "demo"])
    assert r.exit_code == 0, r.output

    r = runner.invoke(app, ["branch", "remove", "demo"])
    assert r.exit_code == 0, r.output
    assert not (repo / ".branches" / "demo").exists()
    assert ".branches/demo" not in _worktrees(repo)
    assert "demo" not in branch_list(repo)


def test_remove_drops_branch_ref(tmp_path, monkeypatch):
    repo = _scratch_repo(tmp_path / "repo")
    monkeypatch.chdir(repo)
    assert runner.invoke(app, ["branch", "create", "demo"]).exit_code == 0
    assert runner.invoke(app, ["branch", "remove", "demo"]).exit_code == 0
    r = subprocess.run(["git", "branch", "--list", "branch/demo"], cwd=repo,
                       capture_output=True, text=True, timeout=60)
    assert r.stdout.strip() == ""


def test_create_outside_git_repo_is_exit_2(tmp_path, monkeypatch):
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.chdir(plain)
    r = runner.invoke(app, ["branch", "create", "demo"])
    assert r.exit_code == 2
    assert "git repository" in r.output


def test_diff_unknown_branch_is_exit_2(tmp_path, monkeypatch):
    repo = _scratch_repo(tmp_path / "repo")
    monkeypatch.chdir(repo)
    r = runner.invoke(app, ["branch", "diff", "nosuch"])
    assert r.exit_code == 2
    assert "no such branch" in r.output


def test_remove_unknown_branch_is_exit_2(tmp_path, monkeypatch):
    repo = _scratch_repo(tmp_path / "repo")
    monkeypatch.chdir(repo)
    r = runner.invoke(app, ["branch", "remove", "nosuch"])
    assert r.exit_code == 2
    assert "no such branch" in r.output


def test_invalid_name_rejected(tmp_path, monkeypatch):
    repo = _scratch_repo(tmp_path / "repo")
    monkeypatch.chdir(repo)
    r = runner.invoke(app, ["branch", "create", "../escape"])
    assert r.exit_code != 0
    assert "invalid branch name" in r.output
    assert not (tmp_path / "escape").exists()


def test_diff_shows_work_after_commit_in_branch(tmp_path, monkeypatch):
    """A committed change on the branch shows up in `branch diff` --stat."""
    repo = _scratch_repo(tmp_path / "repo")
    monkeypatch.chdir(repo)
    assert runner.invoke(app, ["branch", "create", "demo"]).exit_code == 0
    wdir = repo / ".branches" / "demo"
    (wdir / "feature.txt").write_text("new\n")
    subprocess.run(["git", "add", "feature.txt"], cwd=wdir, check=True,
                   timeout=60)
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t",
         "commit", "-m", "feat"], cwd=wdir, check=True, timeout=60,
        capture_output=True)
    out = branch_diff(repo, "demo")
    assert "feature.txt" in out
    r = runner.invoke(app, ["branch", "diff", "demo"])
    assert r.exit_code == 0 and "feature.txt" in r.output
    assert runner.invoke(app, ["branch", "remove", "demo"]).exit_code == 0
