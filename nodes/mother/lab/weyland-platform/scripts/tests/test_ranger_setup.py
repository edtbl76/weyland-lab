"""Tests for ranger_setup.py's policy logic (B233) — the Trino impersonation policy is the control that makes a password
mean anything. Trino authenticates the principal; Ranger then decides whether that principal may BECOME the session user
it names (X-Trino-User). Ranger's default `all - trinouser` policy, broadened to group `public`, let every principal
become anyone, so `analyst` claiming `dbt` ran as dbt (proven on a throwaway trinodb/trino:468 with the live policies,
2026-10-23). The plugin checks impersonation even when principal == user, so dropping `public` locks everyone out; the
fix is the `{USER}` macro: each user may become only itself.

The fixture is live policy 1 as the Trino plugin cached it (policy version 44, read 2026-10-23).
"""
import copy

import ranger_setup as r

ALL_ACCESSES = ["select", "insert", "create", "drop", "delete", "use", "alter", "grant", "revoke", "show",
                "impersonate", "all", "execute", "read_sysinfo", "write_sysinfo"]


def _item(users, groups, accesses):
    return {"users": list(users), "groups": list(groups), "roles": [], "conditions": [], "delegateAdmin": True,
            "accesses": [{"type": a, "isAllowed": True} for a in accesses]}


LIVE_TRINOUSER = {"id": 1, "service": "trino", "name": "all - trinouser", "policyType": 0, "isEnabled": True,
                  "resources": {"trinouser": {"values": ["*"], "isExcludes": False, "isRecursive": False}},
                  "policyItems": [_item(["trino"], ["public"], ["impersonate"])]}
LIVE_TABLE = {"id": 12, "service": "trino", "name": "all - catalog, schema, table", "policyType": 0,
              "isEnabled": True,
              "resources": {"catalog": {"values": ["*"]}, "schema": {"values": ["*"]}, "table": {"values": ["*"]}},
              "policyItems": [_item(["trino"], [], ALL_ACCESSES)]}


def _grants_impersonate_any(p):
    values = p["resources"].get("trinouser", {}).get("values", [])
    return "*" in values and any(a["type"] == "impersonate" for i in p["policyItems"] for a in i["accesses"])


def test_broaden_adds_public_to_an_ordinary_default_policy():
    out = r.broadened(copy.deepcopy(LIVE_TABLE))
    assert out is not None
    assert out["policyItems"][0]["groups"] == ["public"]


def test_broaden_never_touches_the_impersonation_policy():
    p = copy.deepcopy(LIVE_TRINOUSER)
    p["policyItems"][0]["groups"] = []
    assert r.broadened(p) is None  # a rebuild must not hand impersonate-anyone back to public


def test_broaden_is_idempotent():
    once = r.broadened(copy.deepcopy(LIVE_TABLE))
    assert r.broadened(once) is None


def test_self_impersonation_turns_the_live_policy_into_user_macro_for_public():
    out = r.self_impersonation(copy.deepcopy(LIVE_TRINOUSER))
    assert out["resources"]["trinouser"]["values"] == ["{USER}"]
    assert len(out["policyItems"]) == 1
    item = out["policyItems"][0]
    assert item["groups"] == ["public"] and item["users"] == []
    assert [a["type"] for a in item["accesses"]] == ["impersonate"]
    assert item["delegateAdmin"] is False
    assert not _grants_impersonate_any(out)


def test_the_live_policy_is_the_bypass_the_fix_removes():
    assert _grants_impersonate_any(LIVE_TRINOUSER)


def test_self_impersonation_is_idempotent():
    once = r.self_impersonation(copy.deepcopy(LIVE_TRINOUSER))
    assert r.self_impersonation(once) is None


def test_self_impersonation_drops_any_extra_grant_on_the_policy():
    p = copy.deepcopy(LIVE_TRINOUSER)
    p["policyItems"].append(_item(["dbt"], [], ["impersonate"]))
    out = r.self_impersonation(p)
    assert len(out["policyItems"]) == 1 and out["policyItems"][0]["users"] == []


def test_is_trinouser_policy():
    assert r.is_trinouser_policy(LIVE_TRINOUSER)
    assert not r.is_trinouser_policy(LIVE_TABLE)


def test_service_config_reaches_trino_over_verified_https_as_ranger(monkeypatch):
    monkeypatch.setenv("TRINO_PW_RANGER", "pw")
    cfg = r.service_configs()
    assert cfg["username"] == "ranger" and cfg["password"] == "pw"
    url = cfg["jdbc.url"]
    assert url.startswith("jdbc:trino://trino.data-mesh.svc.cluster.local:8443")
    assert "SSL=true" in url and "SSLVerification=FULL" in url
    assert "SSLTrustStorePath=/etc/weyland-ca/rootCA.pem" in url
    # Trino JDBC 451 (the driver Ranger 2.6 ships) detects a PEM file by itself; SSLTrustStoreType=PEM fails with
    # "PEM KeyStore not available" (observed against the throwaway, 2026-10-23).
    assert "SSLTrustStoreType" not in url


def test_service_config_without_the_lookup_password_still_names_ranger(monkeypatch):
    monkeypatch.delenv("TRINO_PW_RANGER", raising=False)
    cfg = r.service_configs()
    assert cfg["username"] == "ranger" and cfg["password"] == ""
