"""Tests for register_bifrost_client_config.py (B202) — the Bifrost client_config settings the lab owns.

Three settings: `/metrics` stays public under the v2.2.6 setup lock (whitelisted_routes), CORS is limited to the
dashboard's own origin (allowed_origins), and every inference call needs a virtual key (enforce_auth_on_inference).
PUT /api/config copies many client_config fields unconditionally (booleans such as drop_excess_requests,
disable_content_logging), so a partial body would silently reset them. The script must round-trip the FULL
client_config it read, change only the owned fields, and never send framework_config or auth_config (both are left
alone when absent). The fake below records exactly what would be PUT.
"""
import pytest

import register_bifrost_client_config as r

BASE_CC = {"drop_excess_requests": True, "disable_content_logging": False, "prometheus_labels": [],
           "mcp_server_auth_mode": "headers", "whitelisted_routes": None, "allowed_origins": None,
           "enforce_auth_on_inference": False, "skills_external_client_url": "", "mcp_external_client_url": ""}
LIVE = {"client_config": BASE_CC, "framework_config": {"pricing_url": "x"}, "auth_config": {"is_enabled": False}}
DONE = {"whitelisted_routes": ["/metrics"], "allowed_origins": ["https://bifrost.weyland.lab"],
        "enforce_auth_on_inference": True, "skills_external_client_url": "https://bifrost.weyland.lab",
        "mcp_external_client_url": "https://bifrost.weyland.lab"}


class _Resp:
    def __init__(self, status, body=None):
        self.status_code, self._body, self.text = status, body, str(body)

    def json(self):
        return self._body


class _Fake:
    def __init__(self, configs, put_status=200):
        self.configs, self.put_status, self.puts = list(configs), put_status, []

    def get(self, path):
        assert path == "/api/config"
        return _Resp(200, self.configs.pop(0) if len(self.configs) > 1 else self.configs[0])

    def put(self, path, json):
        assert path == "/api/config"
        self.puts.append(json)
        return _Resp(self.put_status, {"ok": True})


def _with(**fields):
    return {**LIVE, "client_config": {**BASE_CC, **fields}}


def test_sets_every_owned_field_and_round_trips_the_rest():
    fake = _Fake([_with(), _with(**DONE)])
    assert r.ensure_settings(fake).startswith("updated:")
    (body,) = fake.puts
    assert set(body) == {"client_config"}                      # never framework_config / auth_config
    assert body["client_config"] == {**BASE_CC, **DONE}


def test_keeps_existing_list_entries_and_appends():
    fake = _Fake([_with(whitelisted_routes=["/api/foo"], allowed_origins=["http://localhost:3000"]),
                  _with(**{**DONE, "whitelisted_routes": ["/api/foo", "/metrics"],
                           "allowed_origins": ["http://localhost:3000", "https://bifrost.weyland.lab"]})])
    r.ensure_settings(fake)
    cc = fake.puts[0]["client_config"]
    assert cc["whitelisted_routes"] == ["/api/foo", "/metrics"]
    assert cc["allowed_origins"] == ["http://localhost:3000", "https://bifrost.weyland.lab"]


def test_the_inference_auth_flag_is_always_sent_explicitly():
    # Bifrost applies enforce_auth_on_inference only when the key is PRESENT in the body (an omitted key keeps the
    # stored value), so a full round-trip must carry it as a real boolean.
    fake = _Fake([_with(**{**DONE, "enforce_auth_on_inference": False}), _with(**DONE)])
    r.ensure_settings(fake)
    assert fake.puts[0]["client_config"]["enforce_auth_on_inference"] is True


def test_already_settled_is_a_no_op():
    fake = _Fake([_with(**DONE)])
    assert r.ensure_settings(fake) == "unchanged: client_config already as owned"
    assert fake.puts == []


def test_a_rejected_put_fails_loudly():
    with pytest.raises(SystemExit, match="PUT /api/config 400"):
        r.ensure_settings(_Fake([_with()], put_status=400))


def test_a_read_back_that_did_not_take_fails_closed():
    # the PUT said OK but the stored config is not what we asked for → not success
    with pytest.raises(SystemExit, match="read-back"):
        r.ensure_settings(_Fake([_with(), _with(whitelisted_routes=["/metrics"])]))


def test_main_without_the_url_fails_before_any_call(monkeypatch):
    monkeypatch.delenv("BIFROST_URL", raising=False)
    with pytest.raises(SystemExit, match="BIFROST_URL is not set"):
        r.main()


def test_a_locked_read_fails_with_the_token_hint():
    class Locked(_Fake):
        def get(self, path):
            return _Resp(401, {"error": "setup token required"})
    with pytest.raises(SystemExit, match="BIFROST_SETUP_TOKEN"):
        r.ensure_settings(Locked([LIVE]))


def test_the_skills_marketplace_url_is_set_so_the_marketplace_serves():
    # B241: unset, Bifrost answers 503 "skills marketplace disabled: configure skills_external_client_url" on every
    # marketplace route, and it never derives the URL from Host headers, so it must be stored explicitly.
    fake = _Fake([_with(**{**DONE, "skills_external_client_url": ""}), _with(**DONE)])
    assert r.ensure_settings(fake).startswith("updated:")
    assert fake.puts[0]["client_config"]["skills_external_client_url"] == "https://bifrost.weyland.lab"


def test_the_marketplace_url_as_bifrost_stores_it_counts_as_set():
    # Observed live 2026-11-08 (v2.3.1): a plain string PUT is stored and read back as an env-var object
    # {"value": ..., "type": "plain_text"} (the same field takes env./vault references). The first live run wrote the
    # value, then failed its read-back because it compared that object with the string.
    stored = {"value": "https://bifrost.weyland.lab", "type": "plain_text"}
    fake = _Fake([_with(**{**DONE, "skills_external_client_url": stored})])
    assert r.ensure_settings(fake) == "unchanged: client_config already as owned"
    assert fake.puts == []


def test_an_env_reference_is_not_the_owned_value():
    stored = {"value": "env.BIFROST_SKILLS_URL", "type": "env"}
    fake = _Fake([_with(**{**DONE, "skills_external_client_url": stored}), _with(**DONE)])
    assert r.ensure_settings(fake).startswith("updated:")


def test_the_mcp_oauth_callback_base_is_the_public_url():
    # B192 (2026-11-11): unset, Bifrost builds MCP OAuth redirect_uris from the request Host header. The registrar runs
    # in-cluster, so Jam was registered with http://bifrost.weyland.svc.cluster.local:8080/api/oauth/callback, which no
    # browser can reach. Stored explicitly, every DCR client gets the public callback.
    fake = _Fake([_with(**{**DONE, "mcp_external_client_url": ""}), _with(**DONE)])
    assert r.ensure_settings(fake).startswith("updated:")
    assert fake.puts[0]["client_config"]["mcp_external_client_url"] == "https://bifrost.weyland.lab"


def test_a_different_marketplace_url_is_corrected():
    fake = _Fake([_with(**{**DONE, "skills_external_client_url": "http://localhost:8080"}), _with(**DONE)])
    r.ensure_settings(fake)
    assert fake.puts[0]["client_config"]["skills_external_client_url"] == "https://bifrost.weyland.lab"
