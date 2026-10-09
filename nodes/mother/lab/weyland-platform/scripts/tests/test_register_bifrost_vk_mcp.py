"""Tests for register_bifrost_vk_mcp.py (B203) — virtual-key → MCP-client scoping through Bifrost's v2 API.

The fixtures use the shapes observed live on 2026-10-09 (v2.2.6): `GET /api/governance/virtual-keys` returns
`{virtual_keys: [{id, name, mcp_configs: [{id, mcp_client_id, tools_to_execute, mcp_client: {name, …}}]}], total_count}`
and `GET /api/mcp/clients` returns `{clients: [{config: {name, …}, state, …}], total_count}`. A PUT's `mcp_configs` is
the key's WHOLE set (observed: `[]` revoked a grant), so the script always sends the full desired set, never a delta.
"""
import pytest

import register_bifrost_vk_mcp as r

CLIENTS = ["weyland_fleet", "Context7", "Hugging_Face", "Linear", "Perplexity", "Playwright", "GitHub_Remote",
           "Agent_Memory", "Excalidraw", "Malwarebytes"]
IDS = {n: i + 1 for i, n in enumerate(CLIENTS)}


def _cfg(name, tools=("*",), row=None):
    return {"id": row or 100 + IDS[name], "virtual_key_id": "vk", "mcp_client_id": IDS[name],
            "tools_to_execute": list(tools), "mcp_client": {"id": IDS[name], "name": name}}


def _vk(vid, name, configs):
    return {"id": vid, "name": name, "is_active": True, "mcp_configs": configs}


def _settled():
    return [
        _vk("v1", "coding-agents", [_cfg(n) for n in r.SCOPING["coding-agents"]]),
        _vk("v2", "operator", [_cfg("Excalidraw"), _cfg("Malwarebytes"), _cfg("Agent_Memory", r.MEMORY_READ)]),
        _vk("v3", "chat-eval", []),
        _vk("v4", "realm-llm", []),
    ]


class _Resp:
    def __init__(self, status, body=None):
        self.status_code, self._body, self.text = status, body, str(body)

    def json(self):
        return self._body


class _Fake:
    """Serves the key list (re-read after each PUT) and records every PUT body."""

    def __init__(self, vks, clients=CLIENTS, put_status=200, apply=True):
        self.vks, self.clients, self.put_status, self.apply, self.puts = vks, clients, put_status, apply, []

    def get(self, path, params=None):
        if path == "/api/governance/virtual-keys":
            return _Resp(200, {"virtual_keys": self.vks, "count": len(self.vks), "total_count": len(self.vks)})
        if path == "/api/mcp/clients":
            rows = [{"config": {"name": n}, "state": "healthy"} for n in self.clients]
            return _Resp(200, {"clients": rows, "count": len(rows), "total_count": len(rows)})
        raise AssertionError(path)

    def put(self, path, json):
        vid = path.rsplit("/", 1)[1]
        self.puts.append((vid, json))
        if self.apply and self.put_status < 300:
            vk = next(v for v in self.vks if v["id"] == vid)
            vk["mcp_configs"] = [_cfg(c["mcp_client_name"], c.get("tools_to_execute") or ["*"]) for c in json["mcp_configs"]]
        return _Resp(self.put_status, {"ok": True})


def test_settled_keys_are_unchanged_and_nothing_is_written():
    fake = _Fake(_settled())
    lines, rc = r.reconcile(fake)
    assert rc == 0 and fake.puts == []
    assert all("unchanged" in ln for ln in lines if ln.split()[0] in r.SCOPING)


def test_a_missing_grant_is_put_as_the_full_set_and_read_back():
    vks = _settled()
    vks[0]["mcp_configs"] = vks[0]["mcp_configs"][:-1]          # coding-agents lost Agent_Memory
    fake = _Fake(vks)
    lines, rc = r.reconcile(fake)
    assert rc == 0
    ((vid, body),) = fake.puts
    assert vid == "v1"
    assert [c["mcp_client_name"] for c in body["mcp_configs"]] == r.SCOPING["coding-agents"]   # the full set
    assert set(body) == {"mcp_configs"}                                                       # nothing else touched
    assert any(ln.startswith("coding-agents") and "updated" in ln for ln in lines)


def test_existing_rows_keep_their_ids_so_unchanged_grants_are_updated_not_recreated():
    vks = _settled()
    vks[1]["mcp_configs"] = [_cfg("Excalidraw", row=36), _cfg("Malwarebytes", row=37)]     # operator lost Agent_Memory
    fake = _Fake(vks)
    r.reconcile(fake)
    (_, body), = fake.puts
    ids = {c["mcp_client_name"]: c.get("id") for c in body["mcp_configs"]}
    assert ids == {"Excalidraw": 36, "Malwarebytes": 37, "Agent_Memory": None}


def test_partial_tool_scoping_round_trips_and_order_alone_is_not_a_change():
    vks = _settled()
    vks[1]["mcp_configs"][2]["tools_to_execute"] = list(reversed(r.MEMORY_READ))
    fake = _Fake(vks)
    _, rc = r.reconcile(fake)
    assert rc == 0 and fake.puts == []


def test_a_widened_tool_list_is_narrowed_back():
    vks = _settled()
    vks[1]["mcp_configs"][2]["tools_to_execute"] = ["*"]       # operator's memory became read-write
    fake = _Fake(vks)
    r.reconcile(fake)
    (_, body), = fake.puts
    mem = next(c for c in body["mcp_configs"] if c["mcp_client_name"] == "Agent_Memory")
    assert sorted(mem["tools_to_execute"]) == sorted(r.MEMORY_READ)


def test_an_extra_grant_is_revoked_and_chat_eval_stays_toolless():
    vks = _settled()
    vks[2]["mcp_configs"] = [_cfg("Context7")]
    fake = _Fake(vks)
    r.reconcile(fake)
    (vid, body), = fake.puts
    assert vid == "v3" and body == {"mcp_configs": []}


def test_keys_outside_the_scoping_are_never_touched():
    vks = _settled()
    vks[3]["mcp_configs"] = [_cfg("Context7")]                 # realm-llm is not ours to scope
    fake = _Fake(vks)
    _, rc = r.reconcile(fake)
    assert rc == 0 and fake.puts == []


def test_a_client_not_registered_fails_and_its_key_is_not_written():
    vks = _settled()
    vks[0]["mcp_configs"] = []
    fake = _Fake(vks, clients=[c for c in CLIENTS if c != "Linear"])
    lines, rc = r.reconcile(fake)
    assert rc == 1
    assert all(vid != "v1" for vid, _ in fake.puts)            # never drop Linear silently
    assert any("Linear" in ln and "not registered" in ln for ln in lines)


def test_a_missing_key_fails():
    vks = [v for v in _settled() if v["name"] != "operator"]
    _, rc = r.reconcile(_Fake(vks))
    assert rc == 1


def test_a_put_that_did_not_take_fails_on_read_back():
    vks = _settled()
    vks[0]["mcp_configs"] = []
    lines, rc = r.reconcile(_Fake(vks, apply=False))
    assert rc == 1 and any("read-back" in ln for ln in lines)


def test_a_rejected_put_fails():
    vks = _settled()
    vks[0]["mcp_configs"] = []
    lines, rc = r.reconcile(_Fake(vks, put_status=400))
    assert rc == 1 and any("PUT" in ln and "400" in ln for ln in lines)


def test_a_short_key_list_is_refused():
    class Short(_Fake):
        def get(self, path, params=None):
            resp = super().get(path, params)
            if path == "/api/governance/virtual-keys":
                resp._body["total_count"] = 9
            return resp
    with pytest.raises(SystemExit, match="partial"):
        r.reconcile(Short(_settled()))


def test_a_locked_api_fails_with_the_token_hint():
    class Locked(_Fake):
        def get(self, path, params=None):
            return _Resp(401, {"error": "setup token required"})
    with pytest.raises(SystemExit, match="BIFROST_SETUP_TOKEN"):
        r.reconcile(Locked(_settled()))


def test_main_without_the_url_fails_before_any_call(monkeypatch):
    monkeypatch.delenv("BIFROST_URL", raising=False)
    with pytest.raises(SystemExit, match="BIFROST_URL is not set"):
        r.main()
