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

import requests

BASE = os.environ.get("RANGER_URL", "http://ranger-admin.data-mesh.svc.cluster.local:6080")
# SEC-1: no baked-in fallback (see .env.example). This most often runs during a Ranger REBUILD — i.e. while authz is
# already down — so fail with an actionable message instead of a bare KeyError. Ranger UI users need upper+lower+digit.
ADMIN_PW = os.environ.get("RANGER_ADMIN_PASSWORD")
if not ADMIN_PW:
    sys.exit(
        "RANGER_ADMIN_PASSWORD is not set.\n"
        "  1. source the creds locally:  set -a; . scripts/.env; set +a     (copy scripts/.env.example first)\n"
        "  2. pass it THROUGH the exec — the pod does not have it:\n"
        "     kubectl -n weyland exec -i deploy/dagster-user-code -- \\\n"
        "       env RANGER_ADMIN_PASSWORD=\"$RANGER_ADMIN_PASSWORD\" python - < scripts/ranger_setup.py"
    )
AUTH = (os.environ.get("RANGER_ADMIN_USER", "admin"), ADMIN_PW)
H = {"Content-Type": "application/json"}
TRINO_JDBC = "jdbc:trino://trino.data-mesh.svc.cluster.local:8080"


def _get(path):
    return requests.get(f"{BASE}{path}", auth=AUTH, timeout=20)


def _post(path, body):
    return requests.post(f"{BASE}{path}", auth=AUTH, headers=H, data=json.dumps(body), timeout=20)


def _put(path, body):
    return requests.put(f"{BASE}{path}", auth=AUTH, headers=H, data=json.dumps(body), timeout=20)


def ensure_service():
    if _get("/service/public/v2/api/service/trino").status_code == 200:
        print("service trino: exists")
        return
    svc = {"name": "trino", "type": "trino", "isEnabled": True,
           "configs": {"username": "trino", "password": "",
                       "jdbc.driverClassName": "io.trino.jdbc.TrinoDriver", "jdbc.url": TRINO_JDBC}}
    print("service trino:", _post("/service/public/v2/api/service", svc).status_code)


def broaden_defaults_to_public():
    """Add group `public` to every default ACCESS policy (policyType 0) — anti-lockout for default-deny."""
    pols = _get("/service/public/v2/api/service/trino/policy").json()
    n = 0
    for p in pols:
        if p.get("policyType", 0) != 0:
            continue
        changed = False
        for item in p.get("policyItems", []):
            if "public" not in item.get("groups", []):
                item.setdefault("groups", []).append("public")
                changed = True
        if changed and _put(f"/service/public/v2/api/policy/{p['id']}", p).status_code == 200:
            n += 1
    print(f"broadened {n} default policies to public")


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
    ensure_user("analyst")
    ensure_mask_policy()
    print("ranger trino setup done")
