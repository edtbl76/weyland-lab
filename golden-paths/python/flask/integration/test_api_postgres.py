"""Flask's own integration test (B261): its HTTP API with REAL Postgres behind it.

The framework-neutral adapter tests are test_items_backends.py (a synced copy, shared by every Python path); this file
is the one part that is Flask's: the wiring from the routes through app.extensions to the Postgres store.
"""
import os

import items_backends
import main


def _app():
    return main.create_app(main.Settings(greeting="hi"),
                           items_backends.PostgresItemStore(os.environ["GOLDEN_DATABASE_URL"]))


def test_the_http_api_runs_on_postgres_and_survives_a_restart():
    app = _app()
    try:
        c = app.test_client()
        made = c.post("/items", json={"name": "flask-pg", "tags": ["x"]}).get_json()
        assert c.get(f"/items/{made['id']}").get_json() == made
        assert made in c.get("/items?limit=100").get_json()["items"]
        assert c.get("/items/999999999").get_json()["error"]["code"] == "not_found"
    finally:
        main.app_shutdown(app)
    again = _app()                                        # a new process's view: it was stored
    try:
        assert again.test_client().get(f"/items/{made['id']}").get_json() == made
    finally:
        main.app_shutdown(again)
