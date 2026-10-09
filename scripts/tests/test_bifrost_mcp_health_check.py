"""Tests for bifrost_mcp_health_check.py (B203) — alert when a Bifrost MCP client is not healthy.

Fixtures use the shape observed live 2026-10-09 (v2.2.6): `GET /api/mcp/clients` returns
`{clients: [{config: {name, disabled, …}, state, tools, vk_configs}], count, limit, offset, total_count}` and pages at 25.
A healthy client's `state` is `healthy` (v1 said `connected`); v2.1 adds `last_failure` when a client failed.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path

import bifrost_mcp_health_check as w  # noqa: E402


def _client(name, state="healthy", disabled=False, last_failure=None):
    c = {"config": {"name": name, "disabled": disabled}, "state": state, "tools": [], "vk_configs": []}
    if last_failure:
        c["last_failure"] = last_failure
    return c


def _api(clients, page=25, total=None, status=200):
    """A fake GET that pages like Bifrost (limit/offset) and can lie about total_count."""
    calls = []

    def get(path, params):
        calls.append((path, dict(params)))
        if status != 200:
            return status, {"error": "setup token required"}
        off = params.get("offset", 0)
        rows = clients[off:off + page]
        return 200, {"clients": rows, "count": len(rows), "limit": page, "offset": off,
                     "total_count": len(clients) if total is None else total}
    get.calls = calls
    return get


# --- verdicts ------------------------------------------------------------------------------------------------------

def test_all_healthy_is_silent():
    assert w.verdicts([_client("Context7"), _client("Linear")]) == []


def test_an_unhealthy_client_is_named_with_its_state():
    (v,) = w.verdicts([_client("Context7"), _client("Linear", state="disconnected")])
    assert v[0] == "Linear" and "disconnected" in v[1]


def test_last_failure_detail_is_carried_into_the_reason():
    lf = {"stage": "connect", "message": "oauth token expired", "at": "2026-10-09T03:00:00Z"}
    (v,) = w.verdicts([_client("Hugging_Face", state="needs_reauth", last_failure=lf)])
    assert "needs_reauth" in v[1] and "connect" in v[1] and "oauth token expired" in v[1]


def test_a_disabled_client_is_deliberately_off_and_not_alerted():
    assert w.verdicts([_client("Excalidraw", state="disconnected", disabled=True)]) == []


def test_a_missing_state_is_not_healthy():
    c = _client("Perplexity"); del c["state"]
    assert [v[0] for v in w.verdicts([c])] == ["Perplexity"]


def test_drill_marks_one_named_healthy_client_and_only_that_one():
    (v,) = w.verdicts([_client("Context7"), _client("Linear")], drill="Context7")
    assert v[0] == "Context7" and v[1].startswith("DRILL")


def test_a_drill_naming_no_client_is_refused():
    with pytest.raises(w.CannotRead, match="drill"):
        w.verdicts([_client("Context7")], drill="Nope")


# --- reading the list (fail closed) --------------------------------------------------------------------------------

def test_list_pages_until_total():
    clients = [_client(f"c{i}") for i in range(30)]
    get = _api(clients, page=25)
    assert len(w.list_clients(get)) == 30
    assert [p["offset"] for _, p in get.calls] == [0, 25]


def test_an_empty_list_is_refused():
    with pytest.raises(w.CannotRead, match="no MCP clients"):
        w.list_clients(_api([]))


def test_a_short_list_is_refused():
    with pytest.raises(w.CannotRead, match="partial"):
        w.list_clients(_api([_client("a"), _client("b")], total=5))


def test_a_locked_api_is_refused_with_the_token_hint():
    with pytest.raises(w.CannotRead, match="BIFROST_SETUP_TOKEN"):
        w.list_clients(_api([_client("a")], status=401))


# --- alert + main --------------------------------------------------------------------------------------------------

def test_alert_payload_names_the_client_and_points_at_the_runbook():
    (a,) = w.alert_payload("Linear", "state disconnected")
    assert a["labels"]["alertname"] == "BifrostMCPClientUnhealthy"
    assert a["labels"]["mcp_client"] == "Linear" and a["labels"]["source"] == "bifrost-mcp-watchdog"
    assert "mcp-gateway.md" in a["annotations"]["description"]


def _run(monkeypatch, clients, post_fails=False, **env):
    base = {"BIFROST_URL": "http://b", "BIFROST_SETUP_TOKEN": "t", "ALERTMANAGER_URL": "http://am"}
    for k, v in {**base, **env}.items():
        if v is None:
            monkeypatch.delenv(k, raising=False)
        else:
            monkeypatch.setenv(k, v)
    posted = []
    monkeypatch.setattr(w, "_bifrost", lambda url, token: _api(clients))

    def post(url, body):
        if post_fails:
            raise OSError("connection refused")
        posted.append(body)
    monkeypatch.setattr(w, "_post_alert", post)
    return w.main([]), posted


def test_main_healthy_exits_0_and_posts_nothing(monkeypatch):
    rc, posted = _run(monkeypatch, [_client("Context7"), _client("Linear")])
    assert rc == 0 and posted == []


def test_main_posts_one_alert_per_unhealthy_client(monkeypatch):
    rc, posted = _run(monkeypatch, [_client("Context7"), _client("Linear", "disconnected"), _client("HF", "error")])
    assert rc == 0 and [p[0]["labels"]["mcp_client"] for p in posted] == ["Linear", "HF"]


def test_main_undelivered_alert_exits_1(monkeypatch):
    rc, _ = _run(monkeypatch, [_client("Linear", "disconnected")], post_fails=True)
    assert rc == 1


def test_main_missing_config_exits_2(monkeypatch):
    rc, _ = _run(monkeypatch, [_client("a")], BIFROST_SETUP_TOKEN=None)
    assert rc == 2


def test_main_unreadable_list_exits_2(monkeypatch):
    rc, _ = _run(monkeypatch, [])
    assert rc == 2


def test_main_drill_posts_exactly_one(monkeypatch):
    rc, posted = _run(monkeypatch, [_client("Context7"), _client("Linear")], DRILL_CLIENT="Linear")
    assert rc == 0 and len(posted) == 1 and posted[0][0]["labels"]["drill"] == "true"
