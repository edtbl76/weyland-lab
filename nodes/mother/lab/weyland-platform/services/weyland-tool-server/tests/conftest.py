import pytest


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
