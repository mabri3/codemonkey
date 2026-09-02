"""Print the opencode API key for the unblock proxy to stdout.

Used by with_unblock.sh. Never prints anything else — stdout feeds
CODEMONKEY_UNBLOCK_KEY directly.
"""
import json
from pathlib import Path

print(json.loads((Path.home() / ".local/share/opencode/auth.json").read_text())["opencode"]["key"])
