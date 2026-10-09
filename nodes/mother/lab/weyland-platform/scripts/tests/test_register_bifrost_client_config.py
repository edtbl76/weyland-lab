"""Tests for register_bifrost_client_config.py (B202) — keep Bifrost's /metrics public under the v2.2.6 setup lock.

PUT /api/config copies many client_config fields unconditionally (booleans such as drop_excess_requests,
disable_content_logging), so a partial body would silently reset them. The script must round-trip the FULL
client_config it read, change only whitelisted_routes, and never send framework_config or auth_config (both are
left alone when absent). The fake below records exactly what would be PUT.
"""
import pytest

import register_bifrost_client_config as r

LIVE = {"client_config": {"drop_excess_requests": True, "disable_content_logging": False, "prometheus_labels": [],
                          "mcp_server_auth_mode": "headers", "whitelisted_routes": None},
        "framework_config": {"pricing_url": "x"}, "auth_config": {"is_enabled": False}}


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


def _with(routes):
    return {**LIVE, "client_config": {**LIVE["client_config"], "whitelisted_routes": routes}}


def test_adds_metrics_and_round_trips_every_other_field():
    fake = _Fake([_with(None), _with(["/metrics"])])
    assert r.ensure_routes(fake) == "updated: whitelisted_routes = ['/metrics']"
    (body,) = fake.puts
    assert set(body) == {"client_config"}                      # never framework_config / auth_config
    assert body["client_config"] == {**LIVE["client_config"], "whitelisted_routes": ["/metrics"]}


def test_keeps_existing_routes_and_appends():
    fake = _Fake([_with(["/api/foo"]), _with(["/api/foo", "/metrics"])])
    r.ensure_routes(fake)
    assert fake.puts[0]["client_config"]["whitelisted_routes"] == ["/api/foo", "/metrics"]


def test_already_present_is_a_no_op():
    fake = _Fake([_with(["/metrics"])])
    assert r.ensure_routes(fake) == "unchanged: /metrics already whitelisted"
    assert fake.puts == []


def test_a_rejected_put_fails_loudly():
    with pytest.raises(SystemExit, match="PUT /api/config 400"):
        r.ensure_routes(_Fake([_with(None)], put_status=400))


def test_a_read_back_without_the_route_fails_closed():
    # the PUT said OK but the stored config does not carry the route → not success
    with pytest.raises(SystemExit, match="read-back"):
        r.ensure_routes(_Fake([_with(None), _with(None)]))


def test_main_without_the_url_fails_before_any_call(monkeypatch):
    monkeypatch.delenv("BIFROST_URL", raising=False)
    with pytest.raises(SystemExit, match="BIFROST_URL is not set"):
        r.main()


def test_a_locked_read_fails_with_the_token_hint():
    class Locked(_Fake):
        def get(self, path):
            return _Resp(401, {"error": "setup token required"})
    with pytest.raises(SystemExit, match="BIFROST_SETUP_TOKEN"):
        r.ensure_routes(Locked([LIVE]))
