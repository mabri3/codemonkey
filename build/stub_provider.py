"""Stub OpenAI-compatible provider for CLI-addressable probes (102F6).

Serves a SCRIPTED turn sequence over real HTTP so the RELEASED BINARY can
run a full exec path (CLI → exec → loop → tools → journal) with zero
product changes and no model endpoint:

    python build/stub_provider.py PORT turns.json

turns.json: {"turns": ["<assistant content>", ...]} — the Nth
POST /chat/completions returns turns[N]; past the end, the LAST turn
repeats (lets stuck-detectors/advisories fire honestly). GET /v1/models
answers so provider standup succeeds. Honors `stream:true` with SSE
(`delta.content` chunks + `[DONE]`), plain JSON otherwise.

Only stdlib. Test tooling — never imported by src/.
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

TURNS: list = []


class Handler(BaseHTTPRequestHandler):
    server_version = "stub-provider"

    def log_message(self, format, *args):  # noqa: A002 (stdlib signature)
        pass

    def _send(self, payload: bytes, ctype: str):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            self._send(json.dumps({"data": [{"id": "stub"}]}).encode(),
                       "application/json")
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            body = {}
        state = self.server._stub_state  # type: ignore[attr-defined]
        idx = min(state["n"], len(TURNS) - 1)
        state["n"] += 1
        content = TURNS[idx] if TURNS else "done"
        if body.get("stream"):
            chunks = [
                {"choices": [{"delta": {"content": content[: len(content) // 2 + 1]},
                              "index": 0}]},
                {"choices": [{"delta": {"content": content[len(content) // 2 + 1:]},
                              "index": 0}]},
                {"choices": [{"delta": {}, "index": 0, "finish_reason": "stop"}]},
            ]
            sse = "".join("data: " + json.dumps(c) + "\n\n" for c in chunks)
            sse += "data: [DONE]\n\n"
            self._send(sse.encode(), "text/event-stream")
        else:
            self._send(json.dumps({
                "choices": [{"message": {"content": content},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 5,
                          "total_tokens": 10},
            }).encode(), "application/json")


def main(argv: list) -> int:
    global TURNS
    port = int(argv[1])
    with open(argv[2]) as f:
        TURNS = json.load(f)["turns"]
    assert TURNS, "script needs at least one turn"
    server = HTTPServer(("127.0.0.1", port), Handler)
    server._stub_state = {"n": 0}  # type: ignore[attr-defined]
    server.serve_forever()
    return 0  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
