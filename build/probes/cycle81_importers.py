"""Cycle 81 helper: importer map for every src/codemonkey module."""
import re
from pathlib import Path

src = Path("/Users/bharris/Programs/CodeMonkey/src/codemonkey")
mods = sorted(p.stem for p in src.glob("*.py") if p.stem != "__init__")
files = [p for p in src.rglob("*.py") if "__pycache__" not in str(p)]

for mod in mods:
    pats = [
        re.compile(rf"from\s+(\.|codemonkey\.){mod}\s+import"),
        re.compile(rf"import\s+codemonkey\.{mod}\b"),
        re.compile(rf"from\s+\.+{mod}\s+import"),
        re.compile(rf"from\s+\.+\s+import\s+[^\n]*\b{mod}\b"),
        re.compile(rf"from\s+codemonkey\s+import\s+[^\n]*\b{mod}\b"),
    ]
    importers = set()
    for f in files:
        if f.stem == mod:
            continue
        try:
            text = f.read_text()
        except OSError:
            continue
        if any(p.search(text) for p in pats):
            try:
                importers.add(f.relative_to(src).as_posix())
            except ValueError:
                importers.add(f.name)
    print(f"{mod}: {sorted(importers) if importers else 'NO-SRC-IMPORTER'}")
