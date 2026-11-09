"""The APISIX gateway's routes, as code, compared against and restored to etcd (B239 finding 18). Stdlib only.

APISIX (traditional role, etcd config provider) reads routes and upstreams from etcd keys `/apisix/routes/<id>` and
`/apisix/upstreams/<id>`, each a JSON record. These are the desired records, copied from the live values observed
2026-11-08: one upstream (the tool-server) and five prefix routes onto it. Timestamps are ignored when comparing.
Runbook: docs/runbooks/apisix.md.
"""
from __future__ import annotations

import json
from typing import Callable

UPSTREAM_KEY = "/apisix/upstreams/1"
ROUTES = [("1", "context", "/context"), ("2", "pipeline", "/pipeline"), ("3", "qdrant", "/qdrant"),
          ("4", "weaviate", "/weaviate"), ("5", "neo4j", "/neo4j")]
IGNORED = {"create_time", "update_time"}


def desired_records(now: int) -> dict[str, dict]:
    """Every desired key and its record, upstream first (a route must not point at a missing upstream)."""
    recs = {UPSTREAM_KEY: {
        "id": "1", "name": "weyland-tool-server", "type": "roundrobin", "hash_on": "vars", "pass_host": "pass",
        "scheme": "http", "nodes": {"weyland-tool-server.weyland.svc.cluster.local:8080": 1},
        "create_time": now, "update_time": now,
    }}
    for rid, name, prefix in ROUTES:
        recs[f"/apisix/routes/{rid}"] = {
            "id": rid, "name": name, "uri": f"{prefix}/*", "upstream_id": "1", "status": 1, "priority": 0,
            "plugins": {"prometheus": {"prefer_name": False}}, "create_time": now, "update_time": now,
        }
    return recs


def _comparable(rec: dict) -> dict:
    return {k: v for k, v in rec.items() if k not in IGNORED}


def drift(get: Callable[[str], str | None]) -> list[tuple[str, str]]:
    """(key, problem) for every desired record that is missing, unreadable or different in etcd."""
    out = []
    for key, want in desired_records(0).items():
        raw = get(key)
        if not raw:
            out.append((key, "missing"))
            continue
        try:
            have = json.loads(raw)
        except ValueError:
            out.append((key, "unreadable value"))
            continue
        want_c, have_c = _comparable(want), _comparable(have)
        changed = sorted(k for k in set(want_c) | set(have_c) if want_c.get(k) != have_c.get(k))
        if changed:
            out.append((key, "differs: " + ", ".join(changed)))
    return out


def restore(get: Callable[[str], str | None], put: Callable[[str, str], None], now: int) -> list[str]:
    """Write every drifted record (upstream first); return the keys written."""
    bad = {key for key, _ in drift(get)}
    written = []
    for key, rec in desired_records(now).items():
        if key in bad:
            put(key, json.dumps(rec, separators=(",", ":")))
            written.append(key)
    return written
