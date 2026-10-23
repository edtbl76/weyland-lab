#!/usr/bin/env python3
"""Codify the Ranger→Trino authz setup (L5 Slice A) so it survives a Ranger rebuild — the service, policies, and
users are otherwise UI/API state that dies with the Ranger DB. Idempotent-enough (re-POSTs of existing objects
return 400 "already exists", which is fine — this file is the source-of-truth for the desired state).

Creates: the `trino` service; broadens the 13 default access policies to group `public` (so the mesh's varied
Trino users — dbt/lightdash/trino/... — aren't locked out by default-deny); the `analyst` demo user; the
`depression_pct` column-mask policy (analyst sees NULL, everyone else the real value).

Run from a pod that can reach ranger-admin and has `requests` (the dagster user-code pod). RANGER_ADMIN_PASSWORD is
REQUIRED (no fallback) and must be passed THROUGH the exec — the pod doesn't have it. Source scripts/.env first:
  kubectl -n weyland exec -i deploy/dagster-user-code -- env RANGER_ADMIN_PASSWORD="$RANGER_ADMIN_PASSWORD" python - < scripts/ranger_setup.py
"""
import json
import os
import secrets
import sys

BASE = os.environ.get("RANGER_URL", "http://ranger-admin.data-mesh.svc.cluster.local:6080")
H = {"Content-Type": "application/json"}
# B233: Trino takes a password only over HTTPS (8443, a cert from the lab's mkcert CA). Ranger Admin's resource lookup
# logs in as `ranger` (TRINO_PW_RANGER, from scripts/trino-credentials.sh) and verifies the cert against the CA mounted
# at /etc/weyland-ca (k8s/data-mesh/ranger.yaml). No SSLTrustStoreType: the driver Ranger ships (trino-jdbc 451) detects a
# PEM file itself, and `PEM` as a type fails ("PEM KeyStore not available", observed 2026-10-23).
TRINO_JDBC = ("jdbc:trino://trino.data-mesh.svc.cluster.local:8443?SSL=true&SSLVerification=FULL"
              "&SSLTrustStorePath=/etc/weyland-ca/rootCA.pem")


def _auth():
    # SEC-1: no baked-in fallback (see .env.example). This most often runs during a Ranger REBUILD — i.e. while authz is
    # already down — so fail with an actionable message instead of a bare KeyError. Checked at run time, not import, so
    # the policy logic below is testable without a credential.
    admin_pw = os.environ.get("RANGER_ADMIN_PASSWORD")
    if not admin_pw:
        sys.exit(
            "RANGER_ADMIN_PASSWORD is not set.\n"
            "  1. source the creds locally:  set -a; . scripts/.env; set +a     (copy scripts/.env.example first)\n"
            "  2. pass it THROUGH the exec — the pod does not have it:\n"
            "     kubectl -n weyland exec -i deploy/dagster-user-code -- \\\n"
            "       env RANGER_ADMIN_PASSWORD=\"$RANGER_ADMIN_PASSWORD\" python - < scripts/ranger_setup.py"
        )
    return (os.environ.get("RANGER_ADMIN_USER", "admin"), admin_pw)


def _get(path):
    import requests
    return requests.get(f"{BASE}{path}", auth=_auth(), timeout=20)


def _post(path, body):
    import requests
    return requests.post(f"{BASE}{path}", auth=_auth(), headers=H, data=json.dumps(body), timeout=20)


def _put(path, body):
    import requests
    return requests.put(f"{BASE}{path}", auth=_auth(), headers=H, data=json.dumps(body), timeout=20)


def service_configs():
    return {"username": "ranger", "password": os.environ.get("TRINO_PW_RANGER", ""),
            "jdbc.driverClassName": "io.trino.jdbc.TrinoDriver", "jdbc.url": TRINO_JDBC}


def ensure_service():
    r = _get("/service/public/v2/api/service/trino")
    if r.status_code != 200:
        svc = {"name": "trino", "type": "trino", "isEnabled": True, "configs": service_configs()}
        print("service trino:", _post("/service/public/v2/api/service", svc).status_code)
        return
    svc = r.json()
    want = service_configs()
    if all(svc.get("configs", {}).get(k) == v for k, v in want.items() if k != "password") and not want["password"]:
        print("service trino: exists, lookup config current")
        return
    svc["configs"] = {**svc.get("configs", {}), **want}
    print("service trino: lookup config updated:", _put(f"/service/public/v2/api/service/{svc['id']}", svc).status_code)


def is_trinouser_policy(p):
    return "trinouser" in p.get("resources", {})


def broadened(p):
    """The policy with group `public` added to every item, or None if nothing changes. Never the impersonation policy:
    `public` there means every principal may become ANY user, which turns X-Trino-User back into a free claim."""
    if p.get("policyType", 0) != 0 or is_trinouser_policy(p):
        return None
    changed = False
    for item in p.get("policyItems", []):
        if "public" not in item.get("groups", []):
            item.setdefault("groups", []).append("public")
            changed = True
    return p if changed else None


def self_impersonation(p):
    """The impersonation policy rewritten so each principal may become only itself (`{USER}`), or None if it already is.
    Trino's Ranger plugin checks impersonation even when principal == session user, so an empty policy locks everyone
    out; `{USER}` for `public` is the one grant every caller needs and the only one it gets (B233)."""
    want_item = {"users": [], "groups": ["public"], "roles": [], "conditions": [], "delegateAdmin": False,
                 "accesses": [{"type": "impersonate", "isAllowed": True}]}
    values = p["resources"]["trinouser"].get("values")
    items = p.get("policyItems", [])
    if values == ["{USER}"] and len(items) == 1 and all(items[0].get(k) == v for k, v in want_item.items()):
        return None
    p["resources"]["trinouser"]["values"] = ["{USER}"]
    p["policyItems"] = [want_item]
    return p


def broaden_defaults_to_public():
    """Add group `public` to every default ACCESS policy (policyType 0) — anti-lockout for default-deny."""
    n = 0
    for p in _get("/service/public/v2/api/service/trino/policy").json():
        out = broadened(p)
        if out and _put(f"/service/public/v2/api/policy/{p['id']}", out).status_code == 200:
            n += 1
    print(f"broadened {n} default policies to public")


def restrict_impersonation_to_self():
    pols = [p for p in _get("/service/public/v2/api/service/trino/policy").json() if is_trinouser_policy(p)]
    if not pols:
        sys.exit("no trinouser policy found in service trino — refusing to report success")
    for p in pols:
        out = self_impersonation(p)
        if out is None:
            print(f"impersonation policy {p['id']}: already self-only")
            continue
        code = _put(f"/service/public/v2/api/policy/{p['id']}", out).status_code
        if code != 200:
            sys.exit(f"impersonation policy {p['id']}: update failed ({code})")
        print(f"impersonation policy {p['id']}: now {{USER}} only")


def ensure_user(name):
    # Do NOT reuse the admin credential for provisioned accounts. These users exist only so policies can REFERENCE
    # them — authz is evaluated on the Trino session user and nobody logs in as them — so a throwaway random
    # password is correct. The "Aa1" suffix guarantees Ranger's upper+lower+digit requirement.
    u = {"name": name, "password": secrets.token_urlsafe(24) + "Aa1", "firstName": name.title(), "lastName": "Demo",
         "userRoleList": ["ROLE_USER"], "status": 1, "isVisible": 1}
    print(f"user {name}:", _post("/service/xusers/secure/users", u).status_code)


def ensure_mask_policy():
    pol = {"service": "trino", "name": "mask-depression-pct-analyst", "policyType": 1, "isEnabled": True,
           "resources": {"catalog": {"values": ["iceberg"]}, "schema": {"values": ["dbt"]},
                         "table": {"values": ["mart_state_health_trends"]}, "column": {"values": ["depression_pct"]}},
           "dataMaskPolicyItems": [{"users": ["analyst"], "accesses": [{"type": "select", "isAllowed": True}],
                                    "dataMaskInfo": {"dataMaskType": "MASK_NULL"}}]}
    print("mask policy:", _post("/service/public/v2/api/policy", pol).status_code)


if __name__ == "__main__":
    ensure_service()
    broaden_defaults_to_public()
    restrict_impersonation_to_self()
    ensure_user("analyst")
    ensure_mask_policy()
    print("ranger trino setup done")
