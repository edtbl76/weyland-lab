"""B62 — AI-dev usage data product, Dagster INGEST asset (mirrors B37 / aidlc_kb_ingest).

Reads per-session summary JSONs from the MinIO `ai-sessions` bucket (produced on rogueone by
scripts/ai_session_feeder.py) and upserts one `ai_session` entity per session into Port. Own
group ("ai_session") + on-demand/scheduled job, same shape as the aidlc-kb ingest. Mirrors B37's
empty-read guard: 0 objects read => treat as a MinIO/auth blip, skip the Port upsert entirely
(never act destructively on an empty read).

Source carries metrics only — no conversation content ever leaves rogueone (the producer
summarises locally; only the summaries are shipped to MinIO).
"""
import json
import os
import urllib.request

from dagster import asset, Output, MetadataValue

# Properties mirrored onto the Port `ai_session` blueprint (relation `service` handled separately).
_PORT_FIELDS = (
    "project", "started_at", "ended_at", "duration_minutes", "user_turns", "assistant_turns",
    "input_tokens", "output_tokens", "cache_read_tokens", "cache_creation_tokens", "total_tokens",
    "models", "tools_invoked", "api_equiv_value_usd",
)


def _read_minio_sessions(log) -> list:
    """Pull every session-summary JSON out of the MinIO `ai-sessions` bucket (B37 _read_minio_docs twin)."""
    from minio import Minio

    endpoint = os.environ.get("MINIO_ENDPOINT", "minio.minio.svc.cluster.local:9000")
    bucket = os.environ.get("AI_SESSIONS_BUCKET", "ai-sessions")
    secure = os.environ.get("MINIO_SECURE", "false").lower() == "true"
    client = Minio(
        endpoint,
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=secure,
    )

    sessions: list = []
    for obj in client.list_objects(bucket, recursive=True):
        if not obj.object_name.endswith(".json"):
            continue
        resp = client.get_object(bucket, obj.object_name)
        try:
            sessions.append(json.loads(resp.read().decode("utf-8")))
        finally:
            resp.close()
            resp.release_conn()
    log.info("ai_session: read %d session summaries from MinIO bucket '%s'", len(sessions), bucket)
    return sessions


def _port_token() -> str:
    base = os.environ.get("PORT_API_BASE", "https://api.port.io")
    body = json.dumps({
        "clientId": os.environ["PORT_CLIENT_ID"],
        "clientSecret": os.environ["PORT_CLIENT_SECRET"],
    }).encode()
    req = urllib.request.Request(f"{base}/v1/auth/access_token", body,
                                 {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())["accessToken"]


def _port_upsert(token: str, s: dict) -> None:
    base = os.environ.get("PORT_API_BASE", "https://api.port.io")
    entity = {
        "identifier": s["session_id"],
        "title": f'{s["project"]} · {s["started_at"][:10]}',
        "properties": {k: s[k] for k in _PORT_FIELDS if k in s},
    }
    if s.get("service"):
        entity["relations"] = {"service": s["service"]}
    url = (f"{base}/v1/blueprints/ai_session/entities"
           "?upsert=true&merge=true&create_missing_related_entities=false")
    req = urllib.request.Request(url, json.dumps(entity).encode(),
                                 {"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    urllib.request.urlopen(req).read()


@asset(
    group_name="ai_session",
    description="Ingest Claude Code AI-dev session summaries from MinIO (ai-sessions bucket) and upsert one "
                "ai_session entity per session into Port. Producer: scripts/ai_session_feeder.py on rogueone. "
                "B37-style empty-read guard (0 objects => skip, never touch Port).",
)
def ai_session_ingest(context) -> Output:
    log = context.log
    sessions = _read_minio_sessions(log)

    if not sessions:
        log.warning("ai_session: 0 summaries read from MinIO — skipping Port upsert (likely a MinIO/auth blip).")
        return Output({"skipped": True, "reason": "empty MinIO read"},
                      metadata={"sessions_read": 0, "skipped": MetadataValue.bool(True)})

    token = _port_token()
    ok = err = 0
    by_project: dict = {}
    for s in sessions:
        try:
            _port_upsert(token, s)
            ok += 1
            by_project[s["project"]] = by_project.get(s["project"], 0) + 1
        except Exception as e:  # one bad session must not abort the run
            err += 1
            log.error("ai_session: upsert failed for %s: %s", s.get("session_id"), e)

    summary = {"sessions_read": len(sessions), "upserted": ok, "errors": err, "by_project": by_project}
    log.info("ai_session summary: %s", summary)
    return Output(summary, metadata={
        "sessions_read": MetadataValue.int(len(sessions)),
        "upserted": MetadataValue.int(ok),
        "errors": MetadataValue.int(err),
        "by_project": MetadataValue.json(by_project),
    })
