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


def load(chat_id: int) -> tuple[list, dict | None]:
    """Return (history, pending_action) for a chat — history is [(role, text), ...] (empty if new), pending_action
    is the proposal awaiting confirmation (or None). psycopg2 decodes the JSONB columns to Python for us."""
    def q(cur):
        cur.execute("SELECT history, pending_action FROM operator_sessions WHERE chat_id = %s", (chat_id,))
        row = cur.fetchone()
        if not row:
            return [], None
        history = [tuple(t) for t in row[0]] if row[0] else []
        return history, row[1]
    return _run(q)


def save(chat_id: int, history: list, pending_action: dict | None = None) -> None:
    """Upsert the chat history (trimmed to the last MAX_TURNS turns) and the pending_action (None clears it)."""
    payload = json.dumps([list(t) for t in history[-(MAX_TURNS * 2):]])
    pending = json.dumps(pending_action) if pending_action is not None else None
    _run(lambda cur: cur.execute(
        "INSERT INTO operator_sessions (chat_id, history, pending_action, updated_at) VALUES (%s, %s, %s, now()) "
        "ON CONFLICT (chat_id) DO UPDATE SET history = EXCLUDED.history, "
        "pending_action = EXCLUDED.pending_action, updated_at = now()",
        (chat_id, payload, pending)))


# --- B45 incident-sweep dedup (operator_incidents) — notify once per firing episode ------------------------------
_INCIDENTS_DDL = """
CREATE TABLE IF NOT EXISTS operator_incidents (
    fingerprint TEXT PRIMARY KEY,
    alertname   TEXT,
    instance    TEXT,
    notified_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


def init_incidents() -> None:
    """Ensure the incident dedup table exists (idempotent)."""
    _run(lambda cur: cur.execute(_INCIDENTS_DDL))


def incidents_recorded() -> set:
    """Fingerprints of incidents already enriched + notified (still-firing episodes we've handled)."""
    def q(cur):
        cur.execute("SELECT fingerprint FROM operator_incidents")
        return {r[0] for r in cur.fetchall()}
    return _run(q)


def incident_record(fingerprint: str, labels: dict) -> None:
    """Mark an incident notified so the next sweep doesn't re-notify it."""
    _run(lambda cur: cur.execute(
        "INSERT INTO operator_incidents (fingerprint, alertname, instance, notified_at) VALUES (%s, %s, %s, now()) "
        "ON CONFLICT (fingerprint) DO NOTHING",
        (fingerprint, labels.get("alertname", ""), labels.get("instance") or labels.get("pod") or "")))


def incidents_clear_resolved(active: set) -> None:
    """Delete records for alerts no longer firing, so a later re-fire notifies again."""
    def q(cur):
        cur.execute("SELECT fingerprint FROM operator_incidents")
        gone = [fp for (fp,) in cur.fetchall() if fp not in active]
        if gone:
            cur.execute("DELETE FROM operator_incidents WHERE fingerprint = ANY(%s)", (gone,))
    _run(q)
