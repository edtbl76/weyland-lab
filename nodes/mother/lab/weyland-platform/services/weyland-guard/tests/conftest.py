import sys
import types

import pytest

# app.py imports psycopg2 at MODULE scope (the verdict store), but it's not a guard test dep — the driver is
# only used inside _record_verdict, which the app's fail-open tests never reach (guardrails=None → "allow",
# no scoring, no DB write). Stub it so `import app` works in the slim test lane without the real driver.
if "psycopg2" not in sys.modules:
    _pg = types.ModuleType("psycopg2")
    _pg.connect = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no db in tests"))
    sys.modules["psycopg2"] = _pg


class FakeCursor:
    def __init__(self, store):
        self.store = store

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.store.append((sql, params))

    def fetchone(self):
        return [1]


class FakeConn:
    def __init__(self):
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self):
        return FakeCursor(self.executed)


@pytest.fixture
def fake_conn():
    return FakeConn()
