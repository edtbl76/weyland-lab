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

    def _post(url, json, timeout):
        sent.update(url=url, body=json)
        return _Resp()
    monkeypatch.setattr(realm.httpx, "post", _post)
    out = realm.delegate_to_realm("audit the dashboards")
    assert sent["url"].endswith("/route")
    assert sent["body"] == {"message": "audit the dashboards", "allow_paid": True}
    assert "handled by Odin" in out
