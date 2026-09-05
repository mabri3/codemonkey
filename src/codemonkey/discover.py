"""Repo-declared test-command discovery (loop 40, cycle 94).

ASK DECIDED 2026-09-04: ship default-OFF semantics — discovery only fills
the verifier when the operator configured nothing (explicit param > config
> discovered > none). No declaration → behavior unchanged (no command
invented, no failure). The default-ON flip waits for loop40-final numbers
(discovery hit rate + false-gate rate).

Precedence and source attribution are the whole point: the loop40-final
measurement needs to know WHERE each verifier came from.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def discover_verify_command(workdir: str | Path) -> tuple[str | None, str]:
    """(command, source-file) declared by the repo, or (None, "")."""
    wd = Path(workdir)
    if (wd / "pytest.ini").is_file():
        return "pytest -q", "pytest.ini"
    tox = wd / "tox.ini"
    if tox.is_file():
        return "tox", "tox.ini"
    setup_cfg = wd / "setup.cfg"
    if setup_cfg.is_file():
        try:
            text = setup_cfg.read_text()
        except OSError:
            text = ""
        if "[tool:pytest]" in text:
            return "pytest -q", "setup.cfg"
    pyproject = wd / "pyproject.toml"
    if pyproject.is_file():
        try:
            text = pyproject.read_text()
        except OSError:
            text = ""
        if "[tool.pytest" in text:
            return "pytest -q", "pyproject.toml"
    package_json = wd / "package.json"
    if package_json.is_file():
        try:
            data = json.loads(package_json.read_text())
        except (OSError, ValueError):
            data = {}
        if isinstance(data, dict) and isinstance(data.get("scripts"), dict) \
                and data["scripts"].get("test"):
            return "npm test", "package.json"
    makefile = wd / "Makefile"
    if makefile.is_file():
        try:
            text = makefile.read_text()
        except OSError:
            text = ""
        if re.search(r"^test\s*:", text, re.M):
            return "make test", "Makefile"
    return None, ""


def resolve_verifier(explicit: str | None, configured: str | None,
                     workdir: str | Path) -> tuple[str | None, str]:
    """Precedence: explicit param > config > discovered > none.
    Returns (command, origin) where origin ∈ {"explicit", "config",
    "discovered:<file>", "none"}."""
    if explicit and explicit.strip():
        return explicit.strip(), "explicit"
    if configured and configured.strip():
        return configured.strip(), "config"
    cmd, source = discover_verify_command(workdir)
    if cmd:
        return cmd, f"discovered:{source}"
    return None, "none"
