"""scripts/bifrost-fleet-txn.py — the ship's end-to-end MCP transaction through Bifrost (2026-10-16).

Why: a compositor ship (git-af3ae0c8, 2026-10-16) went green while every agent's `weyland_fleet` call failed. Bifrost held
an MCP session to the old compositor pod ("session terminated (404)"), then retried without one ("Missing session ID"),
and only a Bifrost restart recovered it. No ship check went through Bifrost, so none could see it.

Shapes OBSERVED 2026-10-16 from rogueone (https://bifrost.weyland.lab/mcp, header x-bf-vk = the ship-txn key):
  initialize      200 application/json, serverInfo {name: bifrost, version: v2.2.6}, NO mcp-session-id (stateless)
  tools/list      200 {"result": {"tools": [{"name": "weyland_fleet-k8s_namespaces_list", ...}]}}  (exactly one)
  tools/call      200 {"result": {"content": [{"type": "text", "text": "APIVERSION KIND NAME ...\\nv1 Namespace weyland Active ..."}]}}
The failure arrived through Claude Code's client as "MCP tool call failed ... session terminated (404)": in the raw
protocol that is a JSON-RPC error or an isError result, so both are failures here.
"""
import importlib.util
import json
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location("bifrost_fleet_txn", Path(__file__).resolve().parents[1] / "bifrost-fleet-txn.py")
t = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(t)

TOOL = "weyland_fleet-k8s_namespaces_list"
TABLE = "APIVERSION   KIND        NAME      STATUS   AGE    LABELS\nv1           Namespace   weyland   Active   135d   x"


def _ok_list():
    return {"jsonrpc": "2.0", "id": 2, "result": {"tools": [{"name": TOOL}]}}


def _ok_call(text=TABLE):
    return {"jsonrpc": "2.0", "id": 3, "result": {"content": [{"type": "text", "text": text}]}}


def test_a_real_answer_naming_the_namespace_is_ok():
    assert t.verdict(_ok_list(), _ok_call()) == "TXN_OK"


def test_a_tool_error_fails_and_names_the_bifrost_restart():
    call = {"jsonrpc": "2.0", "id": 3, "result": {"isError": True, "content": [{"type": "text",
            "text": "transport error: session terminated (404). need to re-initialize"}]}}
    v = t.verdict(_ok_list(), call)
    assert v.startswith("TXN_FAIL") and "session terminated" in v
    assert "rollout restart deploy/bifrost" in v


def test_a_jsonrpc_error_fails():
    call = {"jsonrpc": "2.0", "id": 3, "error": {"code": -32603, "message": "Bad Request: Missing session ID"}}
    v = t.verdict(_ok_list(), call)
    assert v.startswith("TXN_FAIL") and "Missing session ID" in v


def test_an_answer_without_the_namespace_fails():
    # an empty table or an unrelated reply is not proof the fleet answered
    v = t.verdict(_ok_list(), _ok_call("No resources found"))
    assert v.startswith("TXN_FAIL") and "weyland" in v


@pytest.mark.parametrize("tools", [[], [TOOL, "weyland_fleet-k8s_pods_list"]])
def test_the_key_must_see_exactly_its_one_tool(tools):
    # more tools = the key was widened (a leaked copy could do more); none = the grant or the client is gone
    lst = {"jsonrpc": "2.0", "id": 2, "result": {"tools": [{"name": n} for n in tools]}}
    v = t.verdict(lst, _ok_call())
    assert v.startswith("TXN_FAIL") and "exactly" in v


def test_a_missing_key_fails_closed(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("BIFROST_SHIP_TXN_VK", raising=False)
    env = tmp_path / ".env"
    env.write_text("OTHER=1\n")
    assert t.main(["--env-file", str(env)]) == 1          # the ship reads the PRINTED line; the code is for a hand run
    assert capsys.readouterr().out.strip().startswith("TXN_FAIL no BIFROST_SHIP_TXN_VK")


def test_the_key_comes_from_only_its_line_of_the_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("BIFROST_SHIP_TXN_VK", raising=False)
    env = tmp_path / ".env"
    env.write_text("SOMETHING=else\nexport BIFROST_SHIP_TXN_VK='sk-bf-abc'\n")
    assert t.vk_from(str(env)) == "sk-bf-abc"


def test_an_unreachable_bifrost_fails_with_the_reason(monkeypatch, capsys):
    monkeypatch.setenv("BIFROST_SHIP_TXN_VK", "k")

    def boom(*a, **k):
        raise OSError("connection refused")
    monkeypatch.setattr(t, "_post", boom)
    assert t.main([]) == 1
    out = capsys.readouterr().out
    assert out.startswith("TXN_FAIL") and "connection refused" in out


def test_main_runs_initialize_list_call_in_order(monkeypatch, capsys):
    monkeypatch.setenv("BIFROST_SHIP_TXN_VK", "k")
    seen = []

    def fake(url, body, key):
        seen.append(body.get("method"))
        return {"tools/list": _ok_list(), "tools/call": _ok_call()}.get(body.get("method"), {"result": {}})
    monkeypatch.setattr(t, "_post", fake)
    assert t.main([]) == 0
    assert seen == ["initialize", "notifications/initialized", "tools/list", "tools/call"]
    assert capsys.readouterr().out.strip() == "TXN_OK"
