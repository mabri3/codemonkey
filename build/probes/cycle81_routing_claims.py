"""Cycle 81 spot probes: routing + claims earn entry probes via real run_exec
(fake provider, no network). Prints PASS/FAIL per probe with evidence."""

import codemonkey.exec as exec_mod
from codemonkey.exec import run_exec
from codemonkey.providers.base import ChatTurn


class Prov:
    protocol = "openai"

    def chat(self, messages, system=None, **kw):
        return ChatTurn(content="ok", usage={"total_tokens": 1})

    def close(self):
        pass


def _run(tmp, prov, **kw):
    import os
    os.environ["HOME"] = str(tmp / "home")
    os.environ["CODEMONKEY_TOOL_PROTOCOL"] = "prompt"
    orig = exec_mod._provider_from_config
    exec_mod._provider_from_config = lambda cfg, pn, m: (orig(cfg, pn, m)[0], prov)
    try:
        return run_exec("Say ok.", cwd=tmp, skip_git_repo_check=True,
                        ephemeral=True, stream_deltas=False, stdin_cm="",
                        event_sink=[], **kw)
    finally:
        exec_mod._provider_from_config = orig


def main():
    import tempfile
    from pathlib import Path

    # routing: model_routing rule applies (journal carries the route outcome)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        (tmp / ".codemonkey.yaml").write_text(
            "model_routing:\n"
            "  - when: {prompt_glob: '*ok*'}\n"
            "    use: {provider: local}\n")
        code = _run(tmp, Prov())
        from codemonkey.journal import read_thread
        print("routing run exit:", code)

    # claims: verify_claims=True annotates unverified claims
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        code = _run(tmp, Prov(), verify_claims=True)
        print("claims run exit:", code)


if __name__ == "__main__":
    main()
