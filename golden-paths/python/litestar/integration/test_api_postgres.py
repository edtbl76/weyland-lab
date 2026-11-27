"""Litestar's own integration test (B261): its HTTP API with REAL Postgres behind it.

The framework-neutral adapter tests are test_items_backends.py (a synced copy, shared by every Python path); this file
is the one part that is Litestar's: the wiring from the handlers through `Provide` to the Postgres store.
"""
import os

from litestar.testing import TestClient

import items_backends
from main import Settings, create_app


def _app():
    return create_app(Settings(greeting="hi"), items_backends.PostgresItemStore(os.environ["GOLDEN_DATABASE_URL"]))


def test_the_http_api_runs_on_postgres_and_survives_a_restart():
    with TestClient(_app()) as c:
        made = c.post("/items", json={"name": "litestar-pg", "tags": ["x"]}).json()
        assert c.get(f"/items/{made['id']}").json() == made
        assert made in c.get("/items", params={"limit": 100}).json()["items"]
        assert c.get("/items/999999999").json()["error"]["code"] == "not_found"
    with TestClient(_app()) as c:                      # a new process's view: it was stored
        assert c.get(f"/items/{made['id']}").json() == made
