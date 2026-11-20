"""Tests for register_bifrost_realm_agent.py (B249, 2026-11-19) — the Realm behind Bifrost's Agent Gateway.

Three modes, all against Bifrost's admin API (shapes observed on a v2.5.1 throwaway, 2026-11-19):
  ensure-vk  the operator's virtual key `realm-operator` exists; prints ONLY `REALM_GATEWAY_VK=<value>`, for appending to
             scripts/.env (Bifrost ignores a supplied value, so the key is Bifrost's own; the value is returned on read).
  register   the agent `realm` exists as owned: the Realm's in-cluster card, granted to realm-operator ONLY, the gateway
             token sent from Bifrost's env (`runtime_auth` header `X-Realm-Gateway-Token` = `env.REALM_GATEWAY_TOKEN`).
  check      read-only: the same facts, exit 1 on any drift. "Granted to realm-operator only" is the paid-lane rule: the
             Realm honours `allow_paid` only with the token, so any second granted key could spend.
"""
import pytest

import register_bifrost_realm_agent as r

VK = {"id": "vk-1", "name": "realm-operator", "value": "sk-bf-abc"}
OWNED = {"name": "realm", "agent_card_url": r.CARD_URL, "enabled": True, "allow_by_default": False,
         "forward_accepted_credential": False, "virtual_key_ids": ["vk-1"],
         "runtime_auth": {"type": "headers", "headers": {"X-Realm-Gateway-Token":
                                                         {"value": "<REDACTED>", "ref": "env.REALM_GATEWAY_TOKEN", "type": "env"}}}}


class _Resp:
    def __init__(self, status, body=None):
        self.status_code, self._body, self.text = status, body, str(body)

    def json(self):
        return self._body


class _Fake:
    """Records writes; `vks` is the key list, `agent` the stored registration (None = 404)."""
    def __init__(self, vks=(), agent=None, write_status=200):
        self.vks, self.agent, self.write_status, self.writes = list(vks), agent, write_status, []

    def get(self, path):
        if path == "/api/governance/virtual-keys":
            return _Resp(200, {"virtual_keys": self.vks, "count": len(self.vks)})
        if path == "/api/agents/realm":
            return _Resp(404, {"error": {"message": "agent not found"}}) if self.agent is None else _Resp(200, self.agent)
        raise AssertionError(path)

    def post(self, path, json):
        self.writes.append(("POST", path, json))
        if path == "/api/governance/virtual-keys":
            self.vks.append({**VK, "name": json["name"]})
            return _Resp(self.write_status, {"virtual_key": self.vks[-1]})
        if path == "/api/agents":
            self.agent = _stored(json)
            return _Resp(self.write_status, self.agent)
        raise AssertionError(path)

    def put(self, path, json):
        self.writes.append(("PUT", path, json))
        self.agent = _stored(json)
        return _Resp(self.write_status, self.agent)


def _stored(body):
    """What Bifrost reads back: the env-referenced header redacted, the ref kept."""
    out = dict(body)
    ra = body["runtime_auth"]
    out["runtime_auth"] = {"type": ra["type"], "headers": {k: {"value": "<REDACTED>", "ref": v, "type": "env"}
                                                           for k, v in ra["headers"].items()}}
    return out


# ---- ensure-vk ---------------------------------------------------------------------------------------------------
def test_ensure_vk_creates_the_key_and_prints_only_the_env_line(capsys):
    fake = _Fake()
    r.ensure_vk(fake)
    assert fake.writes[0][:2] == ("POST", "/api/governance/virtual-keys") and fake.writes[0][2]["name"] == "realm-operator"
    assert capsys.readouterr().out == "REALM_GATEWAY_VK=sk-bf-abc\n"


def test_ensure_vk_reuses_an_existing_key(capsys):
    fake = _Fake(vks=[VK])
    r.ensure_vk(fake)
    assert fake.writes == [] and capsys.readouterr().out == "REALM_GATEWAY_VK=sk-bf-abc\n"


def test_a_masked_or_empty_value_is_refused_not_printed(capsys):
    fake = _Fake(vks=[{**VK, "value": "sk-bf-****"}])
    with pytest.raises(SystemExit, match="value"):
        r.ensure_vk(fake)
    assert capsys.readouterr().out == ""


# ---- register ----------------------------------------------------------------------------------------------------
def test_register_creates_the_owned_agent_granted_to_the_operator_key_only():
    fake = _Fake(vks=[VK])
    msg = r.register(fake)
    method, path, body = fake.writes[0]
    assert (method, path) == ("POST", "/api/agents")
    assert body["name"] == "realm" and body["agent_card_url"] == r.CARD_URL
    assert body["virtual_key_ids"] == ["vk-1"] and body["allow_by_default"] is False
    assert body["forward_accepted_credential"] is False
    assert body["runtime_auth"] == {"type": "headers", "headers": {"X-Realm-Gateway-Token": "env.REALM_GATEWAY_TOKEN"}}
    assert msg.startswith("registered")


def test_register_puts_when_it_drifted_and_is_a_no_op_when_owned():
    drifted = {**OWNED, "virtual_key_ids": ["vk-1", "vk-other"]}
    fake = _Fake(vks=[VK], agent=drifted)
    assert r.register(fake).startswith("updated")
    assert fake.writes[0][:2] == ("PUT", "/api/agents/realm") and fake.writes[0][2]["virtual_key_ids"] == ["vk-1"]
    owned = _Fake(vks=[VK], agent=OWNED)
    assert r.register(owned) == "unchanged: realm registered as owned" and owned.writes == []


def test_register_without_the_operator_key_fails_before_writing():
    fake = _Fake()
    with pytest.raises(SystemExit, match="ensure-vk"):
        r.register(fake)
    assert fake.writes == []


def test_a_rejected_registration_fails_loudly():
    with pytest.raises(SystemExit, match="400"):
        r.register(_Fake(vks=[VK], write_status=400))


# ---- check -------------------------------------------------------------------------------------------------------
def test_check_passes_on_the_owned_registration(capsys):
    assert r.check(_Fake(vks=[VK], agent=OWNED)) == 0
    assert "OK" in capsys.readouterr().out


@pytest.mark.parametrize("change,reason", [
    ({"virtual_key_ids": ["vk-1", "vk-other"]}, "granted"),           # a second key could spend (the paid-lane rule)
    ({"allow_by_default": True}, "granted"),                          # every key could call it
    ({"runtime_auth": {"type": "none"}}, "token"),                    # the Realm would see no gateway token
    ({"enabled": False}, "enabled"),
])
def test_check_fails_on_drift_and_names_it(capsys, change, reason):
    assert r.check(_Fake(vks=[VK], agent={**OWNED, **change})) == 1
    assert reason in capsys.readouterr().out


def test_check_on_a_missing_agent_is_a_failure(capsys):
    assert r.check(_Fake(vks=[VK], agent=None)) == 1
    assert "not registered" in capsys.readouterr().out


def test_main_rejects_an_unknown_mode():
    with pytest.raises(SystemExit, match="usage"):
        r.main(["bogus"])
