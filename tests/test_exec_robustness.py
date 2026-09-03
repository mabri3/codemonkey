"""Unattended-run robustness (cycle 50).

51F2 — a transport failure printed its `error:` line twice: once from the run's
event stream, once from the CLI's catch-all.
51F3 — `exec PROMPT` blocked on an inherited-but-idle stdin pipe, hanging any
supervisor/CI invocation that does not close stdin.
"""

from __future__ import annotations

import os
import sys
import threading

from codemonkey.exec import _read_optional_stdin
from codemonkey.providers.base import ProviderError


# ---- 51F2: double-reported errors --------------------------------------

def test_provider_error_starts_unreported():
    assert ProviderError("boom").reported is False


def test_reported_flag_is_settable_and_survives_raise():
    exc = ProviderError("boom")
    exc.reported = True
    try:
        raise exc
    except ProviderError as caught:
        assert getattr(caught, "reported", False) is True


# ---- 51F3: optional stdin must never block -----------------------------

def _with_stdin(fd, fn):
    saved = sys.stdin
    sys.stdin = os.fdopen(fd, "r")
    try:
        return fn()
    finally:
        sys.stdin = saved


def test_idle_open_pipe_returns_empty_instead_of_blocking():
    """The exact hang: a writer holds the pipe open and never writes."""
    r, w = os.pipe()  # w stays open for the duration -> no EOF
    try:
        done = []

        def run():
            done.append(_with_stdin(r, lambda: _read_optional_stdin(timeout=0.1)))

        t = threading.Thread(target=run, daemon=True)
        t.start()
        t.join(timeout=10)
        assert not t.is_alive(), "optional stdin read blocked on an idle pipe"
        assert done == [""]
    finally:
        os.close(w)


def test_pipe_with_data_is_still_consumed():
    """The feature must survive: `cat notes | codemonkey exec 'summarize'`."""
    r, w = os.pipe()
    os.write(w, b"some context\n")
    os.close(w)  # real pipelines close, producing EOF
    assert _with_stdin(r, lambda: _read_optional_stdin(timeout=2.0)) == "some context\n"


def test_in_memory_stream_is_read_directly():
    """CliRunner hands us a StringIO with no fileno; it cannot block."""
    import io

    saved = sys.stdin
    sys.stdin = io.StringIO("piped text")
    try:
        assert _read_optional_stdin() == "piped text"
    finally:
        sys.stdin = saved
