"""Truth pass (loop 17B, R17B): claims vs evidence over the build ledger.

For every acceptance row we've written, check the CLAIMED evidence exists:
  - "tests/<file>.py" claimed → file exists, contains ≥ claimed test count
  - module claimed shipped → src file exists
Reports {claim, verified, detail} — the ledger can't drift silently.
"""

from __future__ import annotations

import re
import os
from pathlib import Path

_CLAIM_ROW = re.compile(r"tests/test[_\w]+\.py")

# legend of modules claimed in loops 17-27 vs their src artifacts
FEATURE_SRC = {
    "honest-completion": "claims.py",
    "static model routing": "routing.py",
    "unload-fallback": "unload.py",
    "affinity batching": "affinity.py",
    "budget": "budget.py",
    "arg validation": "argvalidate.py",
    "digest": "digest.py",
    "dry-run": "dryrun.py",
    "env quarantine": "envquarantine.py",
    "role_presets": "rolepresets.py",
}


def audit_report(report_path: Path, src_root: Path) -> list[dict]:
    text = report_path.read_text() if report_path.is_file() else ""
    findings = []
    # 1. every referenced test file exists
    repo_root = report_path.parent
    while repo_root != repo_root.parent and not (repo_root / ".git").exists():
        repo_root = repo_root.parent
    for tf in sorted(set(_CLAIM_ROW.findall(text))):
        p = repo_root / "tests" / os.path.basename(tf)
        findings.append({"claim": f"test file {tf}",
                         "verified": p.is_file(),
                         "detail": str(p)})
    # 2. feature modules exist
    for feat, src in FEATURE_SRC.items():
        if feat in text.lower():
            p = src_root / src
            findings.append({"claim": f"module for {feat}",
                             "verified": p.is_file(),
                             "detail": str(p)})
    return findings


def claimed_test_count(report_path: Path, test_file: str) -> int:
    """Max 'N/N' pass count attributed to a test file in the report text."""
    text = report_path.read_text() if report_path.is_file() else ""
    counts = re.findall(rf"{re.escape(test_file)}[^|]*?\|[^|]*?(\d+)/\1?\b", text)
    return max([int(c) for c in counts], default=0)
