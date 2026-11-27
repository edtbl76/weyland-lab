"""FastAPI's own integration test (B260/B261): its HTTP API with REAL Postgres behind it.

The framework-neutral adapter tests are test_items_backends.py (a synced copy, shared by every Python path); this file
is the one part that is FastAPI's: the wiring from routes through `Depends(get_store)` to the Postgres store.
"""
import os

from fastapi.testclient import TestClient

import items_backends
from main import Settings, create_app


def test_the_http_api_runs_on_postgres_and_survives_a_restart():
    store = items_backends.PostgresItemStore(os.environ["GOLDEN_DATABASE_URL"])
    with TestClient(create_app(Settings(greeting="hi"), store=store)) as c:
        made = c.post("/items", json={"name": "fastapi-pg", "tags": ["x"]}).json()
        assert c.get(f"/items/{made['id']}").json() == made
        assert made in c.get("/items", params={"limit": 100}).json()["items"]
        assert c.get("/items/999999999").json()["error"]["code"] == "not_found"
    again = items_backends.PostgresItemStore(os.environ["GOLDEN_DATABASE_URL"])
    with TestClient(create_app(Settings(greeting="hi"), store=again)) as c:   # a new process's view: it was stored
        assert c.get(f"/items/{made['id']}").json() == made
