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


# B250 (2026-11-19): Lab Recall gets the docs corpus, and ONLY the docs corpus: a second connection to the same
# /mcp-fleet gateway whose allowlist is the one docs-search tool, so Lab Recall cannot reach the live-status tools.

def test_tool_servers_add_a_docs_only_connection_for_lab_recall():
    stale_docs = {"url": "x/mcp-fleet", "info": {"id": "lab-docs"}, "config": {"function_name_filter_list": "k8s_pods_get"}}
    out = oc.desired_tool_servers([stale_docs])
    docs = [c for c in out if c["info"]["id"] == "lab-docs"]
    assert len(docs) == 1
    d = docs[0]
    assert d["url"].endswith("/mcp-fleet") and d["auth_type"] == "system_oauth"
    assert d["config"]["function_name_filter_list"] == "context_context_search"   # full compositor name: suffix match


def test_check_flags_a_docs_connection_with_extra_tools():
    good = oc.desired_tool_servers([])
    labels = dict(oc._check_tool_servers(good))
    assert labels["tool server lab-docs = /mcp-fleet, system_oauth, docs search only"] is True
    widened = [c if c["info"]["id"] != "lab-docs" else
               {**c, "config": {**c["config"], "function_name_filter_list": "context_context_search,k8s_pods_get"}}
               for c in good]
    assert dict(oc._check_tool_servers(widened))["tool server lab-docs = /mcp-fleet, system_oauth, docs search only"] is False


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
    cur = {"id": "lab-recall", "params": {"system": "old prompt", "temperature": 0.2},
           "meta": {"toolIds": ["server:mcp:agent-memory"],
                    "capabilities": {"web_search": True, "image_generation": True, "terminal": True, "vision": True}}}
    out = oc.desired_lab_recall(cur)
    caps = out["meta"]["capabilities"]
    assert caps["web_search"] is caps["image_generation"] is caps["terminal"] is False
    assert caps["vision"] is True and caps["builtin_tools"] is False
    assert out["params"]["temperature"] == 0.2                     # other params kept


def test_lab_recall_gets_memory_and_docs_and_a_prompt_that_falls_back_and_never_guesses():
    out = oc.desired_lab_recall({"id": "lab-recall", "params": {"system": "old prompt"}, "meta": {}})
    assert out["meta"]["toolIds"] == ["server:mcp:agent-memory", "server:mcp:lab-docs"]
    system = out["params"]["system"]
    assert system == oc.LAB_RECALL_SYSTEM
    assert "agent-memory_search_notes" in system and "lab-docs_context_context_search" in system
    assert "acronym" in system and "Lab Status" in system
    # measured 2026-11-19 on the real model and tools (10/10 vs 1/10): read the top note, gate every source on the
    # asked term appearing in it, and run the tools NATIVELY (Open WebUI's default mode allows one tool round)
    assert "agent-memory_read_note on the first result" in system and "singular or plural" in system
    assert out["params"]["function_calling"] == "native"
    # owner, 2026-11-19 ("yes, switch Lab Recall to qwen3:30b-a3b"): same eval, final prompt, real tool schemas —
    # qwen2.5:7b-operator ADR 5/5 QZR 3/5 (never tried docs); qwen3:30b-a3b ADR 5/5 QZR 5/5 (docs searched 5/5)
    assert out["base_model_id"] == "qwen3:30b-a3b"


def test_lab_recall_check_wants_both_tools_and_the_prompt():
    good = oc.desired_lab_recall({"id": "lab-recall", "params": {}, "meta": {}})
    assert oc.lab_recall_ok(good) is True
    memory_only = {**good, "meta": {**good["meta"], "toolIds": ["server:mcp:agent-memory"]}}
    assert oc.lab_recall_ok(memory_only) is False
    old_prompt = {**good, "params": {**good["params"], "system": "old prompt"}}
    assert oc.lab_recall_ok(old_prompt) is False
    default_mode = {**good, "params": {"system": good["params"]["system"]}}   # no function_calling: one tool round
    assert oc.lab_recall_ok(default_mode) is False
    old_model = {**good, "base_model_id": "qwen2.5:7b-operator"}
    assert oc.lab_recall_ok(old_model) is False


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


# ---- speech-to-text (B134 plan step 2, 2026-11-14: whisper moved from CT 103 to timberback) -------------------------
# The STT URL lives in Open WebUI's database (audio.stt.openai.api_base_url), so the deployment's env var only seeds a
# fresh volume: on the live app it pointed at CT 103 after the env var would have changed. The curated state owns it.

def _audio(stt_url="http://192.168.1.246:9000/v1", engine="openai"):
    return {"tts": {"ENGINE": "", "MODEL": "tts-1", "VOICE": "alloy", "OPENAI_API_BASE_URL": "https://api.openai.com/v1"},
            "stt": {"ENGINE": engine, "MODEL": "whisper-1", "OPENAI_API_BASE_URL": stt_url,
                    "OPENAI_API_KEY": "sk-local-whisper", "OPENAI_API_REQUEST_FORMAT": "multipart",
                    "ALLOWED_EXTENSIONS": ["wav", "webm"], "WHISPER_MODEL": "base"},
            "realtime": {"enabled": False}}


def test_audio_points_stt_at_the_in_cluster_whisper_service():
    out = oc.desired_audio(_audio())
    assert out["stt"]["OPENAI_API_BASE_URL"] == "http://whisper.weyland.svc.cluster.local:9000/v1"
    assert out["stt"]["ENGINE"] == "openai" and out["stt"]["MODEL"] == "whisper-1"


def test_audio_keeps_every_other_stt_and_tts_field_and_drops_realtime():
    cur = _audio()
    cur["tts"]["SPLIT_ON"] = "punctuation"
    out = oc.desired_audio(cur)
    assert out["tts"]["SPLIT_ON"] == "punctuation"      # only the engine, URL, key, model and voice are curated
    assert out["stt"]["ALLOWED_EXTENSIONS"] == ["wav", "webm"] and out["stt"]["WHISPER_MODEL"] == "base"
    assert set(out) == {"tts", "stt"}                   # realtime is optional in the update form; never resent


def test_audio_check_flags_the_old_ct_url_and_passes_the_new_one():
    assert oc.stt_ok(_audio()) is False
    assert oc.stt_ok(_audio(stt_url=oc.WHISPER_URL)) is True
    assert oc.stt_ok(_audio(stt_url=oc.WHISPER_URL, engine="")) is False   # local in-app whisper is not the lab's


# ---- text-to-speech (B246, 2026-11-19): the read-aloud button speaks through the lab's Kokoro, never OpenAI's cloud ----
# Live 0.12 default (read 2026-11-19): ENGINE "" (the browser's own voice) and OPENAI_API_BASE_URL api.openai.com.

def test_audio_points_tts_at_the_in_cluster_kokoro_service():
    out = oc.desired_audio(_audio())
    tts = out["tts"]
    assert tts["ENGINE"] == "openai" and tts["OPENAI_API_BASE_URL"] == "http://kokoro.weyland.svc.cluster.local:8880/v1"
    assert tts["MODEL"] == "kokoro" and tts["VOICE"] == "af_heart"
    assert tts["OPENAI_API_KEY"]                        # Kokoro ignores it, but the client sends one


def test_tts_check_flags_openai_cloud_and_the_browser_voice_and_passes_kokoro():
    assert oc.tts_ok(_audio()) is False                                   # the 0.12 default: browser voice, OpenAI URL
    kokoro = oc.desired_audio(_audio())
    assert oc.tts_ok(kokoro) is True
    cloud = {**kokoro, "tts": {**kokoro["tts"], "OPENAI_API_BASE_URL": "https://api.openai.com/v1"}}
    assert oc.tts_ok(cloud) is False
    browser = {**kokoro, "tts": {**kokoro["tts"], "ENGINE": ""}}
    assert oc.tts_ok(browser) is False
    no_voice = {**kokoro, "tts": {**kokoro["tts"], "VOICE": "alloy"}}     # an OpenAI voice name Kokoro does not have
    assert oc.tts_ok(no_voice) is False


# ---- the guarded chat lane (2026-11-19): named for what it is, below the lab models ----------------------------------
# It is NeMo Guardrails over plain gpt-oss:20b, no tools and no lab context. Listed first as "weyland-operator", it was
# taken for the operator and asked for the lab's status, which it invented. Live (read 2026-11-19): no DB entry, so the
# picker showed the connection's raw id.

def test_picker_puts_lab_recall_and_lab_status_before_the_guarded_chat():
    order = oc.MODEL_ORDER
    assert order[:2] == ["lab-recall", "lab-status"]
    assert order.index("weyland-operator") > order.index("lab-status")


def test_guarded_chat_entry_is_named_for_what_it_is_and_public():
    e = oc.desired_guarded_chat(None)
    assert e["id"] == "weyland-operator" and e["base_model_id"] is None and e["is_active"] is True
    assert e["name"] == "Guarded chat (no lab access)"
    assert "Lab Status" in e["meta"]["description"]
    assert e["access_grants"] == [{"principal_type": "user", "principal_id": "*", "permission": "read"}]


def test_guarded_chat_entry_keeps_existing_meta_and_grants():
    existing = {"id": "weyland-operator", "name": "old", "base_model_id": None, "is_active": True, "params": {},
                "meta": {"tags": [{"name": "t"}]}, "access_grants": [{"principal_id": "*", "permission": "read",
                                                                     "principal_type": "user", "id": "g1"}]}
    e = oc.desired_guarded_chat(existing)
    assert e["name"] == "Guarded chat (no lab access)" and e["meta"]["tags"] == [{"name": "t"}]
    assert e["access_grants"] == existing["access_grants"]


def test_guarded_chat_check_wants_the_name():
    assert oc.guarded_chat_ok(None) is False                                    # no entry: the raw id shows
    assert oc.guarded_chat_ok({"name": "weyland-operator"}) is False
    assert oc.guarded_chat_ok(oc.desired_guarded_chat(None)) is True
