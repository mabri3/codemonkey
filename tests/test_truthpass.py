"""R17B truth pass — claims vs evidence over the build ledger."""

from __future__ import annotations

import pytest

from codemonkey.truthpass import (FEATURE_SRC, audit_report,
                                  claimed_test_count)


@pytest.fixture()
def repo_paths(tmp_path):
    (tmp_path / "build").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "codemonkey").mkdir(parents=True)
    return tmp_path


def _setup_repo(tmp_path, report_text, test_files=(), src_files=()):
    report = tmp_path / "build" / "BUILD_REPORT.md"
    report.write_text(report_text)
    (tmp_path / ".git").mkdir()
    for tf in test_files:
        (tmp_path / "tests" / tf).write_text("def test_x(): pass\n")
    # a module must exist for every feature named in the report
    from codemonkey.truthpass import FEATURE_SRC

    lowered = report_text.lower()
    for feat, src in FEATURE_SRC.items():
        if feat in lowered:
            (tmp_path / "src" / "codemonkey" / src).write_text("#\n")
    return report, tmp_path / "src" / "codemonkey"


def test_test_file_claims_verified(repo_paths):
    report, src = _setup_repo(
        repo_paths, "acceptance: tests/test_budget.py 6/6",
        test_files=["test_budget.py"])
    findings = audit_report(report, src)
    assert all(f["verified"] for f in findings), findings


def test_missing_test_file_flagged(repo_paths):
    report, src = _setup_repo(repo_paths, "tests/test_ghost.py 3/3")
    findings = audit_report(report, src)
    bad = [f for f in findings if not f["verified"]]
    assert len(bad) == 1 and "ghost" in bad[0]["claim"]


def test_feature_module_verified(tmp_path):
    import shutil

    (tmp_path / "build").mkdir(parents=True)
    (tmp_path / "src" / "codemonkey").mkdir(parents=True)
    (tmp_path / ".git").mkdir()
    report = tmp_path / "build" / "BUILD_REPORT.md"
    report.write_text("shipped static model routing")
    findings = audit_report(report, tmp_path / "src" / "codemonkey")
    feas = [f for f in findings if "routing" in f["claim"]]
    assert feas and feas[0]["verified"] is False  # src file absent


def test_feature_module_present(repo_paths):
    report, src = _setup_repo(
        repo_paths, "shipped static model routing",
        src_files=[FEATURE_SRC["static model routing"]])
    findings = audit_report(report, src)
    assert all(f["verified"] for f in findings)


def test_claimed_test_count_parse(repo_paths):
    report, src = _setup_repo(repo_paths, "tests/test_budget.py | 6/6 |")
    assert claimed_test_count(report, "test_budget.py") == 6


def test_real_repo_audit_green():
    """Truth pass over the ACTUAL repo: every ledger claim has evidence."""
    from pathlib import Path

    repo = Path(__file__).parent.parent
    findings = audit_report(repo / "build" / "BUILD_REPORT.md",
                            repo / "src" / "codemonkey")
    assert findings, "audit found nothing to check"
    bad = [f for f in findings if not f["verified"]]
    assert not bad, f"drift: {[f['claim'] for f in bad]}"
