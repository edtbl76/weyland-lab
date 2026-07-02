"""store-scaler — the in-cluster executor behind the Port "wake/sleep store" easy button.

The port-agent (outbound Kafka consumer) forwards a Port self-service action run here; this service
validates it against a tight allowlist and flips the target deployment's replica count via the k8s
API. The k8s client uses the in-cluster ServiceAccount (store-scaler), so auth/TLS/token are handled
natively — the agent just does a dumb POST. Reusable for any future "do X in the cluster from Port"
button. See docs/schedules.md and k8s/data-mesh/store-scaler-rbac.yaml.
"""
import json
import logging
import os

from fastapi import FastAPI, HTTPException, Request
from kubernetes import client, config

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("store-scaler")

NAMESPACE = os.environ.get("SCALER_NAMESPACE", "data-mesh")
# HARD allowlist: only these deployments may be scaled, and only to 0/1 (single-instance stores).
# Defense in depth on top of the RBAC Role, which is already scoped to data-mesh deployments/scale.
ALLOWED_STORES = set(
    os.environ.get("SCALER_ALLOWED_STORES", "cockroachdb,mongodb,mysql,gizmosql").split(",")
)

config.load_incluster_config()
_apps = client.AppsV1Api()

app = FastAPI(title="store-scaler")


# Friendly verbs from the Port dropdown → replica count. Keeps the agent mapping a dumb passthrough
# (it forwards properties verbatim) and the wake/sleep→0/1 logic here, where it's testable.
_ACTION_TO_REPLICAS = {"wake": 1, "up": 1, "sleep": 0, "down": 0}


def _find_inputs(obj):
    """Recursively locate the action-inputs dict — the one holding BOTH 'store' and 'action'. The Port
    polling payload nests inputs unpredictably (not the Kafka doc's .payload.properties), so we search
    for them. Requiring both keys together avoids colliding with the action's own 'action' identifier."""
    if isinstance(obj, dict):
        if "store" in obj and "action" in obj:
            return obj
        for v in obj.values():
            hit = _find_inputs(v)
            if hit is not None:
                return hit
    elif isinstance(obj, list):
        for v in obj:
            hit = _find_inputs(v)
            if hit is not None:
                return hit
    return None


def _extract(payload: dict):
    """Pull (store, replicas, action) from either a simple {store, …} body (curl test) OR a full Port
    run payload (inputs found by recursive search wherever the polling message nests them)."""
    if "store" in payload:
        return payload.get("store"), payload.get("replicas"), payload.get("action")
    props = _find_inputs(payload) or {}
    return props.get("store"), props.get("replicas"), props.get("action")


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/scale")
async def scale(request: Request):
    payload = await request.json()
    log.info("received payload: %s", json.dumps(payload)[:2000])  # reveals the real Port message shape
    store, replicas, action = _extract(payload)

    if store not in ALLOWED_STORES:
        raise HTTPException(400, f"store '{store}' not in allowlist {sorted(ALLOWED_STORES)}")

    # Prefer an explicit replicas; otherwise translate the wake/sleep verb.
    if replicas is None and action is not None:
        key = str(action).strip().lower()
        if key not in _ACTION_TO_REPLICAS:
            raise HTTPException(400, f"action '{action}' must be one of {sorted(_ACTION_TO_REPLICAS)}")
        replicas = _ACTION_TO_REPLICAS[key]
    try:
        replicas = int(replicas)
    except (TypeError, ValueError):
        raise HTTPException(400, f"need replicas (0/1) or action (wake/sleep); got replicas={replicas!r} action={action!r}")
    if replicas not in (0, 1):
        raise HTTPException(400, "replicas must be 0 (sleep) or 1 (wake) — these are single-instance stores")

    _apps.patch_namespaced_deployment_scale(
        name=store, namespace=NAMESPACE, body={"spec": {"replicas": replicas}}
    )
    verb = "woke" if replicas == 1 else "slept"
    log.info("%s %s/%s -> replicas=%d", verb, NAMESPACE, store, replicas)
    return {"store": store, "namespace": NAMESPACE, "replicas": replicas, "status": verb}
