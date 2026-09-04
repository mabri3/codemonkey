"""R31: fork-and-branch execution (git worktrees)."""

from __future__ import annotations

import subprocess

import pytest

from codemonkey.branches import (branch_create, branch_diff, branch_list,
                                 branch_remove)


@pytest.fixture()
def grepo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "d@d"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "d"], cwd=tmp_path, check=True)
    (tmp_path / "f.txt").write_text("one\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init",
                    "--no-verify", "--no-gpg-sign"], cwd=tmp_path, check=True,
                   env={"GIT_AUTHOR_NAME": "d", "GIT_COMMITTER_NAME": "d",
                        "GIT_AUTHOR_EMAIL": "d@d", "GIT_COMMITTER_EMAIL": "d@d",
                        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                        "HOME": str(tmp_path)})
    return tmp_path


def test_create_list_remove(grepo):
    res = branch_create(grepo, "exp1")
    assert res["ok"], res
    assert "exp1" in branch_list(grepo)
    rc = branch_remove(grepo, "exp1")
    assert rc["ok"]
    assert "exp1" not in branch_list(grepo)


def test_branch_diff_stat(grepo):
    branch_create(grepo, "exp2")
    out = branch_diff(grepo, "exp2")
    assert isinstance(out, str)  # empty stat is fine (no divergence)


def test_branch_isolation(grepo):
    res = branch_create(grepo, "iso")
    assert res["ok"]
    wtree = grepo / ".branches" / "iso"
    (wtree / "new.txt").write_text("branch work")
    # main workdir must NOT see the branch file
    assert not (grepo / "new.txt").exists()
