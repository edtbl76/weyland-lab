"""delegate_to_realm asks the Realm for the paid lane EXPLICITLY (B209, 2026-10-14).

B209 flips the Realm's `allow_paid` default to false, so an anonymous caller no longer spends Haiku. The operator's
delegate_to_realm exists only on the paid brain (test_agent_failover: the unpaid brain never gets it), so it must now
say so in the request, or every delegation would silently drop to the free local lane.
"""
import realm


class _Resp:
    def raise_for_status(self):
        return None

    def json(self):
        return {"god": "Odin", "role": "r", "realm": "x", "answer": "done"}


def test_delegate_to_realm_requests_the_paid_lane(monkeypatch):
    sent = {}
    monkeypatch.setattr(realm, "REALM_GATEWAY_URL", "")     # not configured: the direct /route path

    def _post(url, json, timeout, headers=None):
        sent.update(url=url, body=json)
        return _Resp()
    monkeypatch.setattr(realm.httpx, "post", _post)
    out = realm.delegate_to_realm("audit the dashboards")
    assert sent["url"].endswith("/route")
    assert sent["body"] == {"message": "audit the dashboards", "allow_paid": True}
    assert "handled by Odin" in out


# ---- B249 (2026-11-19): through Bifrost's Agent Gateway ------------------------------------------------------------
# With REALM_GATEWAY_URL and REALM_GATEWAY_VK set, the operator speaks A2A v1 to the Realm through Bifrost with its own
# virtual key (the Realm is granted to that key only). `allow_paid` rides in the message metadata; the Realm honours it
# only with the token Bifrost adds. A gateway failure is reported, never retried on the direct /route path, so a broken
# gateway cannot quietly bypass the governed one.

GW = "http://bifrost.weyland.svc.cluster.local:8080/agents/a2a/realm/json-rpc"


class _RPC:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise realm.httpx.HTTPStatusError("boom", request=None, response=None)

    def json(self):
        return self.payload


def _gateway(monkeypatch, reply):
    monkeypatch.setattr(realm, "REALM_GATEWAY_URL", GW)
    monkeypatch.setattr(realm, "REALM_GATEWAY_VK", "vk-operator")
    calls = []

    def _post(url, json, timeout, headers=None):
        calls.append({"url": url, "body": json, "headers": headers or {}})
        return reply
    monkeypatch.setattr(realm.httpx, "post", _post)
    return calls


def test_through_the_gateway_with_its_key_as_a2a_v1(monkeypatch):
    ok = _RPC({"jsonrpc": "2.0", "id": "x", "result": {"message": {
        "role": "ROLE_AGENT", "parts": [{"text": "done"}],
        "metadata": {"god": "Odin", "role": "orchestrator", "realm": "Valhalla"}}}})
    calls = _gateway(monkeypatch, ok)
    out = realm.delegate_to_realm("audit the dashboards")
    c = calls[0]
    assert c["url"] == GW and c["headers"]["x-bf-vk"] == "vk-operator"
    body = c["body"]
    assert body["method"] == "SendMessage" and body["jsonrpc"] == "2.0"
    msg = body["params"]["message"]
    assert msg["role"] == "ROLE_USER" and msg["parts"] == [{"text": "audit the dashboards"}] and msg["messageId"]
    assert msg["metadata"] == {"allow_paid": True}
    assert out == "[handled by Odin · orchestrator · Valhalla]\ndone"


def test_a_gateway_error_is_reported_and_not_retried_directly(monkeypatch):
    calls = _gateway(monkeypatch, _RPC({"jsonrpc": "2.0", "id": "x", "error": {"code": -32603, "message": "agent down"}}))
    out = realm.delegate_to_realm("q")
    assert "agent down" in out and out.startswith('{"error"') and len(calls) == 1


def test_a_reply_without_text_is_an_error_not_an_empty_answer(monkeypatch):
    _gateway(monkeypatch, _RPC({"jsonrpc": "2.0", "id": "x", "result": {"message": {"parts": []}}}))
    out = realm.delegate_to_realm("q")
    assert out.startswith('{"error"') and "no text" in out


def test_an_http_failure_is_an_error(monkeypatch):
    _gateway(monkeypatch, _RPC({}, status=503))
    assert realm.delegate_to_realm("q").startswith('{"error"')


def test_gateway_url_without_a_key_uses_the_direct_path(monkeypatch):
    monkeypatch.setattr(realm, "REALM_GATEWAY_URL", GW)
    monkeypatch.setattr(realm, "REALM_GATEWAY_VK", "")
    sent = {}

    def _post(url, json, timeout, headers=None):
        sent["url"] = url
        return _Resp()
    monkeypatch.setattr(realm.httpx, "post", _post)
    realm.delegate_to_realm("q")
    assert sent["url"].endswith("/route")
