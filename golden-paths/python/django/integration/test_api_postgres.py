"""Django's own integration test (B261): its HTTP API with REAL Postgres behind it.

The framework-neutral adapter tests are test_items_backends.py (a synced copy, shared by every Python path); this file
is the one part that is Django's: the wiring from the DRF views through the app state to the Postgres store.
"""
import json
import os

from django.test import Client

import items_backends
import main


def _with_postgres():
    main.configure(main.Settings(greeting="hi"), items_backends.PostgresItemStore(os.environ["GOLDEN_DATABASE_URL"]))
    main.startup()
    return Client()


def test_the_http_api_runs_on_postgres_and_survives_a_restart():
    c = _with_postgres()
    try:
        made = c.post("/items", data=json.dumps({"name": "django-pg", "tags": ["x"]}),
                      content_type="application/json").json()
        assert c.get(f"/items/{made['id']}").json() == made
        assert made in c.get("/items?limit=100").json()["items"]
        assert c.get("/items/999999999").json()["error"]["code"] == "not_found"
    finally:
        main.shutdown()
    c = _with_postgres()                                  # a new process's view: it was stored
    try:
        assert c.get(f"/items/{made['id']}").json() == made
    finally:
        main.shutdown()
