"""Postgres-backed per-chat session memory for the operator (B66 Part 2).

Short-lived connections per op (not a long-lived pool) — deliberate: the operator is meshed, and long-lived
connections through Envoy can stall (the Neo4j-Bolt lesson); a personal chat bot's volume makes per-op connect a
non-issue and sidesteps that failure mode. `pending_action` is created now but only exercised in Part 3 (the act
confirm-step). History is a flat [[role, text], ...] list, trimmed to the last MAX_TURNS turns (user+assistant)."""
import json
import os

import psycopg2

MAX_TURNS = int(os.getenv("OPERATOR_MAX_TURNS", "10"))

_DDL = """
CREATE TABLE IF NOT EXISTS operator_sessions (
    chat_id        BIGINT PRIMARY KEY,
    history        JSONB NOT NULL DEFAULT '[]'::jsonb,
    pending_action JSONB,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


def _connect():
    return psycopg2.connect(
        host=os.getenv("WEYLAND_DB_HOST", "weyland-postgres.weyland.svc.cluster.local"),
        port=os.getenv("WEYLAND_DB_PORT", "5432"),
        dbname=os.environ["WEYLAND_DB_NAME"],
        user=os.environ["WEYLAND_DB_USER"],
        password=os.environ["WEYLAND_DB_PASSWORD"],
        connect_timeout=10,
    )


def _run(fn):
    conn = _connect()
    try:
        with conn, conn.cursor() as cur:   # `with conn` commits (or rolls back) the transaction
            return fn(cur)
    finally:
        conn.close()


def init() -> None:
    """Ensure the session table exists (idempotent — safe to call on every startup)."""
    _run(lambda cur: cur.execute(_DDL))


def load(chat_id: int) -> list:
    """Return the stored [(role, text), ...] history for a chat (empty list if new)."""
    def q(cur):
        cur.execute("SELECT history FROM operator_sessions WHERE chat_id = %s", (chat_id,))
        row = cur.fetchone()
        return [tuple(t) for t in row[0]] if row and row[0] else []
    return _run(q)


def save(chat_id: int, history: list) -> None:
    """Upsert the chat history, trimmed to the last MAX_TURNS turns (2 messages each)."""
    payload = json.dumps([list(t) for t in history[-(MAX_TURNS * 2):]])
    _run(lambda cur: cur.execute(
        "INSERT INTO operator_sessions (chat_id, history, updated_at) VALUES (%s, %s, now()) "
        "ON CONFLICT (chat_id) DO UPDATE SET history = EXCLUDED.history, updated_at = now()",
        (chat_id, payload)))
