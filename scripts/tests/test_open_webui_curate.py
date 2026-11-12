"""Tests for open_webui_curate.py — the curated state of chat.weyland.lab (B116, 2026-11-12).

Open WebUI keeps its settings in its database, not in git, so a restore from an older backup or a rebuilt data volume
silently loses the curation. The script is the one recorded definition: `--check` reports drift, a plain run applies.
These pin the decisions in its pure functions: what "curated" means for each setting, that a request never carries the
fields 0.12 refuses from an API key (MFA), that a change to one tool-server connection or preset leaves the others
alone, and that drift is reported per setting, never as one opaque failure.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path

import open_webui_curate as oc

NEMO = oc.NEMO_URL


def _openai(urls, configs=None):
    return {"ENABLE_OPENAI_API": True, "OPENAI_API_BASE_URLS": urls, "OPENAI_API_KEYS": [""] * len(urls),
            "OPENAI_API_CONFIGS": configs or {str(i): {"enable": True} for i in range(len(urls))}}


def test_openai_keeps_only_nemo_and_its_own_config():
    cur = _openai(["https://api.openai.com/v1", NEMO], {"0": {"enable": True}, "1": {"enable": True, "prefix_id": ""}})
    out = oc.desired_openai(cur)
    assert out["OPENAI_API_BASE_URLS"] == [NEMO]
    assert out["OPENAI_API_CONFIGS"] == {"0": {"enable": True, "prefix_id": ""}}
    assert out["OPENAI_API_KEYS"] == [""]


def test_openai_without_nemo_fails_closed():
    try:
        oc.desired_openai(_openai(["https://api.openai.com/v1"]))
    except oc.CurateError as e:
        assert "nemo-guardrails" in str(e)
    else:
        raise AssertionError("a config without the guarded lane must not be 'fixed' by dropping everything")


def test_admin_config_never_sends_mfa_fields():
    cur = {"ENABLE_MFA": False, "MFA_ALLOW_OAUTH_BYPASS": False, "MFA_ALLOW_TRUSTED_HEADER_BYPASS": False,
           "ENABLE_COMMUNITY_SHARING": True, "JWT_EXPIRES_IN": "10h"}
    out = oc.desired_admin_config(cur)
    assert out["ENABLE_COMMUNITY_SHARING"] is False
    assert not any(k.startswith("ENABLE_MFA") or k.startswith("MFA_") for k in out)
    assert out["JWT_EXPIRES_IN"] == "10h"  # everything else is resent unchanged


def test_tool_servers_replaces_lab_fleet_and_keeps_others():
    memory = {"url": "x/mcp-memory", "info": {"id": "agent-memory"}, "config": {"enable": True}}
    stale_fleet = {"url": "x/mcp-fleet", "info": {"id": "lab-fleet"}, "config": {"function_name_filter_list": "a"}}
    out = oc.desired_tool_servers([memory, stale_fleet])
    assert out[0] == memory
    fleet = [c for c in out if c["info"]["id"] == "lab-fleet"]
    assert len(fleet) == 1 and fleet[0]["config"]["function_name_filter_list"].split(",") == oc.FLEET_TOOLS


def test_fleet_allowlist_has_no_oncall_tool_and_no_memory_duplicates():
    assert "grafana_list_alert_groups" not in oc.FLEET_TOOLS  # Grafana OnCall is not run here: 404
    assert not any(t.startswith("memory_") for t in oc.FLEET_TOOLS)  # agent-memory covers memory


def test_models_config_sets_defaults_and_keeps_unknown_keys():
    cur = {"DEFAULT_MODELS": None, "MODEL_ORDER_LIST": [], "DEFAULT_MODEL_PARAMS": {"temperature": 0.5},
           "DEFAULT_PINNED_MODELS": None}
    out = oc.desired_models_config(cur)
    assert out["DEFAULT_MODELS"] == "lab-recall"
    assert out["MODEL_ORDER_LIST"] == oc.MODEL_ORDER
    assert out["DEFAULT_MODEL_PARAMS"] == {"temperature": 0.5, "num_ctx": 16384}
    assert out["DEFAULT_PINNED_MODELS"] is None


def test_lab_recall_only_switches_off_the_unbacked_capabilities():
    cur = {"id": "lab-recall", "params": {"system": "keep me"},
           "meta": {"toolIds": ["server:mcp:agent-memory"],
                    "capabilities": {"web_search": True, "image_generation": True, "terminal": True, "vision": True}}}
    out = oc.desired_lab_recall(cur)
    caps = out["meta"]["capabilities"]
    assert caps["web_search"] is caps["image_generation"] is caps["terminal"] is False
    assert caps["vision"] is True and caps["builtin_tools"] is False
    assert out["params"]["system"] == "keep me"
    assert out["meta"]["toolIds"] == ["server:mcp:agent-memory"]


def test_lab_status_preset_shape():
    p = oc.desired_lab_status({"vision": True})
    assert p["base_model_id"] == "qwen3:30b-a3b"
    assert "think" not in p["params"]  # the Thinking-2507 build always reasons; think:false leaks it into the answer
    assert "/no_think" not in p["params"]["system"]
    assert 'ALERTS{alertstate="firing"}' in p["params"]["system"]
    assert p["meta"]["toolIds"] == ["server:mcp:lab-fleet"]
    assert p["meta"]["capabilities"]["builtin_tools"] is False
    assert {"principal_type": "user", "principal_id": "*", "permission": "read"} in p["access_grants"]


def test_hidden_model_entry_for_a_new_id_and_an_existing_one():
    new = oc.hidden_entry("gpt-oss:20b-judge", None, "gpt-oss:20b-judge")
    assert new["meta"] == {"hidden": True} and new["base_model_id"] is None
    old = oc.hidden_entry("x", {"id": "x", "meta": {"hidden": False, "tags": ["t"]}}, "x")
    assert old["meta"] == {"hidden": True, "tags": ["t"]}


def test_drift_lists_each_differing_setting():
    want = {"a": 1, "b": [1, 2], "c": {"d": 1}}
    assert oc.drift(want, {"a": 1, "b": [1, 2], "c": {"d": 1}, "extra": 9}) == []
    assert oc.drift(want, {"a": 2, "b": [1], "c": {"d": 1}}) == ["a", "b"]
    assert oc.drift(want, {"a": 1, "b": [1, 2]}) == ["c"]
