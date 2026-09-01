"""Dagster-free Port ``component``-entity reconciliation from the canonical app registry (B78 follow-up).

Every ``applications.yaml`` entry is a Port ``component`` (schema in ``tofu/port/catalog.tf``). B137
removed the OpenTofu ``port_entity`` ``for_each`` that used to create those entities, and
``emit_applications`` (``datahub_emit.py``) writes ONLY to DataHub and ONLY for ``datahub_application:
true`` rows — so a newly-registered pure-compute component could be committed, pass every git-side
check (``scripts/check-app-registry.sh`` reconciles Argo <-> registry, not registry <-> Port), and
never reach the Port catalog. That gap stranded ``lancedb-exporter`` (B78) and ``port-k8s-exporter``
(B145) until a manual API push on 2026-08-31. This module closes it: ``emit_port_components`` (in
``datahub_emit.py``, wired into ``datahub_catalog_emit_job``) upserts EVERY registry component to Port
on each catalog emit — making ``applications.tf``'s "one registry, both surfaces" claim true again.

Deliberately dagster-free and stdlib-only at module scope (``json``/``urllib`` are imported inside the
I/O functions) so the test lane loads it in isolation via the service ``conftest``'s ``load_isolated``.
The pure mapping (``component_entity``, ``reconcile_plan``) carries every DECISION and is unit-tested;
the thin HTTP wrapper is validated by hand against live Port and at runtime.
"""


def component_entity(app):
    """Map ONE ``applications.yaml`` entry to a Port ``component`` blueprint entity.

    - ``identifier`` = the registry ``port_component`` (its Port id) or, absent that, ``key``. These
      differ deliberately for some apps (``operator`` -> ``weyland-operator``), so membership checks
      MUST use this, not the bare key.
    - ``is_data_application`` mirrors ``datahub_application`` (owns cataloged data => also a DataHub
      Application entity); absent => pure-compute => ``False``.
    - ``capabilities`` pass through as the free string array the blueprint declares; an empty/absent
      list contributes no key rather than writing an empty array.
    - ``datahub_application_url`` and ``relations`` are intentionally NOT set here: with
      ``upsert=true&merge=true`` they are preserved when already present, so reconciliation establishes
      and keeps identity WITHOUT clobbering the DataHub-link enrichment the data-apps carry.
    """
    ident = app.get("port_component") or app["key"]
    props = {
        "description": app.get("description", ""),
        "is_data_application": bool(app.get("datahub_application")),
    }
    caps = app.get("capabilities") or []
    if caps:
        props["capabilities"] = caps
    return {
        "identifier": ident,
        "title": app.get("name", ident),
        "blueprint": "component",
        "properties": props,
    }


def reconcile_plan(apps, existing_ids):
    """``(entities_to_upsert, missing_ids)`` for the registry against Port's current component ids.

    Every app becomes an upsert (idempotent under ``merge=true``). ``missing_ids`` are the registry
    components NOT currently in Port — the drift this reconciler closes, surfaced (sorted) so a run can
    LOG what it created rather than silently making the count line up.
    """
    entities = [component_entity(a) for a in apps]
    have = set(existing_ids)
    missing = sorted({e["identifier"] for e in entities} - have)
    return entities, missing


# --- thin HTTP I/O (stdlib) ---------------------------------------------------------------
# Mirrors the ai_session.py Port pattern (token -> upsert). urllib raises on any non-2xx, so a failed
# call surfaces loudly to the caller (emit_port_components under _safe_emit, which warns-not-aborts).

def _port_base():
    import os
    return os.environ.get("PORT_API_BASE", "https://api.port.io")


def port_token():
    import json
    import os
    import urllib.request
    body = json.dumps({
        "clientId": os.environ["PORT_CLIENT_ID"],
        "clientSecret": os.environ["PORT_CLIENT_SECRET"],
    }).encode()
    req = urllib.request.Request(f"{_port_base()}/v1/auth/access_token", body,
                                 {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())["accessToken"]


def existing_component_ids(token):
    import json
    import urllib.request
    req = urllib.request.Request(f"{_port_base()}/v1/blueprints/component/entities",
                                 headers={"Authorization": f"Bearer {token}"})
    data = json.loads(urllib.request.urlopen(req, timeout=30).read())
    return {e["identifier"] for e in data.get("entities", [])}


def upsert_component(token, entity):
    import json
    import urllib.request
    url = (f"{_port_base()}/v1/blueprints/component/entities"
           "?upsert=true&merge=true&create_missing_related_entities=false")
    req = urllib.request.Request(url, json.dumps(entity).encode(),
                                 {"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    urllib.request.urlopen(req, timeout=30).read()


def reconcile(apps, log=None):
    """Token -> read Port's current component ids -> upsert every registry component. Idempotent.

    Returns ``(n_total, missing_ids)`` so the caller can report how many were created (the drift) vs
    merely refreshed. ``log`` (a callable) records the created ids when there was drift.
    """
    token = port_token()
    entities, missing = reconcile_plan(apps, existing_component_ids(token))
    for entity in entities:
        upsert_component(token, entity)
    if log and missing:
        log(f"created {len(missing)} missing component(s): {', '.join(missing)}")
    return len(entities), missing
