"""heartbeat — the rag-index consumer's readiness signal (2026-10-01).

The consumers have no HTTP server, so `Ready` was only "PID 1 is alive" and ship-images' SMOKE gate rightly refused
them. The consumer touches a file on every pass of its poll loop (it polls every second even with no traffic); the
readinessProbe runs `python heartbeat.py check`, which passes only if that file is fresh. These pin the decision.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import heartbeat as hb  # noqa: E402


def test_a_fresh_heartbeat_is_ready(tmp_path):
    p = tmp_path / "ready"
    hb.beat(str(p))
    assert hb.is_fresh(str(p), max_age=60)


def test_a_stale_heartbeat_is_not_ready(tmp_path):
    p = tmp_path / "ready"
    hb.beat(str(p))
    old = os.path.getmtime(p) - 120
    os.utime(p, (old, old))
    assert not hb.is_fresh(str(p), max_age=60)


def test_no_heartbeat_file_is_not_ready(tmp_path):
    # Before the consumer connects and subscribes, the file does not exist: never Ready, never an exception.
    assert not hb.is_fresh(str(tmp_path / "missing"), max_age=60)


def test_check_exits_0_when_fresh_and_1_when_not(tmp_path, monkeypatch):
    p = tmp_path / "ready"
    monkeypatch.setenv("RAG_INDEX_HEARTBEAT", str(p))
    assert hb.main(["check"]) == 1
    hb.beat(str(p))
    assert hb.main(["check"]) == 0


def test_an_unknown_command_is_refused(tmp_path):
    assert hb.main(["bogus"]) == 2
