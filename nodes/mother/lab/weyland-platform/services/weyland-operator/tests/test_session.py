"""Tests for the operator's Postgres session + incident-dedup layer (B66/B45).

session.py builds the SQL the operator's memory and the incident-sweep dedup depend on. Wrong SQL = lost chat
history or duplicate incident pages. We load session.py in isolation with a FAKE psycopg2 (records exact SQL +
params, returns fixture rows) — asserting the real statement built and the real parsed return, not a mock call.
The real DB round-trip is validated live; the query/parse logic is pinned here.
"""
import importlib.util
import json
import os
import sys
import types

import pytest

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # weyland-operator/
os.environ.setdefault("WEYLAND_DB_NAME", "d")
os.environ.setdefault("WEYLAND_DB_USER", "u")
os.environ.setdefault("WEYLAND_DB_PASSWORD", "p")


class _FakeCursor:
    def __init__(self):
        self.calls = []        # [(normalized_sql, params), ...]
        self.one = None        # fetchone() result
        self.many = []         # fetchall() result

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class _FakeConn:
    def __init__(self, cur):
        self.cur = cur

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self):
        return self.cur

    def close(self):
        pass


_CUR = _FakeCursor()
_fake_psycopg2 = types.ModuleType("psycopg2")
_fake_psycopg2.connect = lambda **k: _FakeConn(_CUR)
sys.modules["psycopg2"] = _fake_psycopg2

# Load the REAL session.py by path (the conftest stubs the `session` sibling for incidents tests; we want the
# real module here), running against the fake psycopg2 above.
_spec = importlib.util.spec_from_file_location("session_under_test", os.path.join(_HERE, "session.py"))
session = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(session)


@pytest.fixture(autouse=True)
def _reset():
    _CUR.calls.clear(); _CUR.one = None; _CUR.many = []
    yield


def test_load_new_chat_returns_empty():
    _CUR.one = None
    hist, pending = session.load(42)
    assert hist == [] and pending is None
    sql, params = _CUR.calls[0]
    assert "SELECT history, pending_action FROM operator_sessions WHERE chat_id = %s" in sql
    assert params == (42,)


def test_load_existing_parses_history_into_tuples():
    _CUR.one = [[["user", "hi"], ["assistant", "yo"]], {"tool": "x"}]
    hist, pending = session.load(7)
    assert hist == [("user", "hi"), ("assistant", "yo")]
    assert pending == {"tool": "x"}


def test_save_trims_to_max_turns_and_upserts():
    hist = [("user", str(i)) for i in range(50)]
    session.save(9, hist, {"act": "go"})
    sql, params = _CUR.calls[0]
    assert "INSERT INTO operator_sessions" in sql and "ON CONFLICT (chat_id) DO UPDATE" in sql
    cid, payload, pending = params
    assert cid == 9
    assert len(json.loads(payload)) == session.MAX_TURNS * 2      # history trimmed to the last N turns
    assert json.loads(pending) == {"act": "go"}


def test_save_none_pending_action_is_null():
    session.save(1, [], None)
    _, params = _CUR.calls[0]
    assert params[2] is None                                       # cleared, not the string "null"


def test_incidents_recorded_returns_fingerprint_set():
    _CUR.many = [("fp1",), ("fp2",)]
    assert session.incidents_recorded() == {"fp1", "fp2"}


def test_incident_record_inserts_identity_do_nothing():
    session.incident_record("fp-x", {"alertname": "Foo", "instance": "i1"})
    sql, params = _CUR.calls[0]
    assert "INSERT INTO operator_incidents" in sql and "ON CONFLICT (fingerprint) DO NOTHING" in sql
    assert params == ("fp-x", "Foo", "i1")


def test_incident_record_falls_back_instance_to_pod():
    session.incident_record("fp-y", {"alertname": "Bar", "pod": "p1"})
    _, params = _CUR.calls[0]
    assert params == ("fp-y", "Bar", "p1")


def test_incidents_clear_resolved_deletes_only_gone():
    _CUR.many = [("keep",), ("gone1",), ("gone2",)]
    session.incidents_clear_resolved({"keep"})
    deletes = [c for c in _CUR.calls if "DELETE" in c[0]]
    assert deletes and deletes[0][1] == (["gone1", "gone2"],)


def test_init_creates_sessions_table():
    session.init()
    assert "CREATE TABLE IF NOT EXISTS operator_sessions" in _CUR.calls[0][0]
