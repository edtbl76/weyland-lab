#!/usr/bin/env python3
"""open_webui_curate.py — the curated workspace of chat.weyland.lab (Open WebUI 0.12.x), B116 (2026-11-12).

Open WebUI keeps these settings in its database (webui.db), not in git, so a restore from an older backup or a rebuilt
data volume loses them silently. This script is their one recorded definition.

    open_webui_curate.py --check   read only: print each setting as OK or DRIFT, exit 1 on any drift
    open_webui_curate.py           apply the curated state, then run the same check (exit 1 if anything did not stick)

What "curated" means:
  - connections: the only OpenAI-style connection is the guarded nemo-guardrails lane (no api.openai.com)
  - community sharing off (chats are never shared to openwebui.com); Arena evaluation model off
  - non-chat models hidden from the picker (an embedder, the eval judge, the operator's own variant, a duplicate)
  - the guarded lane (connection id weyland-operator) named "Guarded chat (no lab access)", listed after Lab Recall
    and Lab Status (2026-11-19: taken for the operator, it invented the lab's status)
  - default model Lab Recall; a fixed picker order; default context num_ctx 16384 (Ollama's 4096 default cut every
    chat with tools selected down to ~2,050 tokens, so the model never saw most tool definitions)
  - Lab Recall: no web search / image generation / terminal buttons (nothing is configured behind them); its tools are
    agent-memory and lab-docs (the docs search alone, B250) and its prompt searches memory, then docs, and never
    guesses what an acronym means
  - tool servers: agent-memory (/mcp-memory) and lab-fleet (/mcp-fleet, 13 read-only status tools), both
    system_oauth = each person's own Keycloak token, so every call is audited as them at the MCP gateway
  - the Lab Status preset (qwen3:30b-a3b + the fleet tools)
  - speech-to-text: the OpenAI engine at the in-cluster whisper service on timberback (B134, 2026-11-14); the
    deployment's AUDIO_STT_* env vars only seed a fresh volume, the database copy is what Open WebUI uses
  - text-to-speech (B246, 2026-11-19): the OpenAI engine at the in-cluster Kokoro, model kokoro, voice af_heart; the
    0.12 default is the browser's own voice with api.openai.com as the URL, so read-aloud never left the lab before
    either, but it did not use the lab's voice

Not done here, by design: the primary admin (the first account) cannot be deleted through 0.12 at all; MFA settings
need a human admin session (an API key gets 403), so this script never sends them.

Env: OPEN_WEBUI_API_KEY (an admin's key, from scripts/.env; never printed), OPEN_WEBUI_URL (default
https://chat.weyland.lab). Runbook: docs/runbooks/open-webui.md § Curated workspace.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

NEMO_URL = "http://nemo-guardrails.weyland.svc.cluster.local:8080/v1"
GATEWAY = "http://weyland-mcp-gateway.weyland.svc.cluster.local:8080"
HIDDEN_MODELS = ["nomic-embed-text:latest", "gpt-oss:20b-judge", "qwen2.5:7b-operator", "qwen3-coder:30b-32k"]
LAB_STATUS_BASE = "qwen3:30b-a3b"
MODEL_ORDER = ["lab-recall", "lab-recall-thorough", "lab-status", "weyland-operator", LAB_STATUS_BASE, "qwen3:14b", "gpt-oss:20b",
               "mistral-small3.2:24b", "qwen3-coder:30b", "devstral:latest", "deepseek-coder-v2:16b",
               "qwen2.5vl:latest", "qwen2.5:7b", "llama3.2:3b"]
NUM_CTX = 16384
# The guarded lane (B115): NeMo Guardrails over plain gpt-oss:20b, no tools, no lab context. Its connection id stays
# `weyland-operator`; this entry gives it a name that says what it is (2026-11-19: taken for the operator, it invented
# the lab's status).
GUARDED_ID = "weyland-operator"
GUARDED_NAME = "Guarded chat (no lab access)"
GUARDED_DESCRIPTION = ("General engineering chat behind the lab's guardrails. It cannot see the lab: for its current "
                       "state use Lab Status, for how it works and what was decided use Lab Recall.")
PUBLIC_READ = [{"principal_type": "user", "principal_id": "*", "permission": "read"}]
LAB_RECALL_OFF = ["web_search", "image_generation", "terminal"]
# Full compositor tool names: Open WebUI's function_name_filter_list matches by SUFFIX, so a prefix like "memory_"
# cannot exclude anything; list what is allowed instead. memory_* is covered by agent-memory; grafana OnCall
# (list_alert_groups) is not run here and answers 404.
FLEET_TOOLS = ["k8s_namespaces_list", "k8s_pods_list_in_namespace", "k8s_pods_get", "k8s_pods_log", "k8s_events_list",
               "k8s_nodes_top", "k8s_pods_top", "grafana_query_prometheus", "grafana_query_loki_logs",
               "grafana_search_dashboards", "datahub_search", "trino_execute_query", "context_context_search"]
ADMIN_CONFIG = "/api/v1/auths/admin/config"
MODELS_CONFIG = "/api/v1/configs/models"
TOOL_SERVERS = "/api/v1/configs/tool_servers"
MODEL_UPDATE = "/api/v1/models/model/update"
MODEL_CREATE = "/api/v1/models/create"
AUDIO_CONFIG = "/api/v1/audio/config"
WHISPER_URL = "http://whisper.weyland.svc.cluster.local:9000/v1"
KOKORO_URL = "http://kokoro.weyland.svc.cluster.local:8880/v1"
KOKORO_VOICE = "af_heart"
MFA_FIELDS = ("ENABLE_MFA", "MFA_ALLOW_OAUTH_BYPASS", "MFA_ALLOW_TRUSTED_HEADER_BYPASS")
DOCS_TOOL = "context_context_search"   # full compositor name: function_name_filter_list matches by suffix
LAB_RECALL_TOOLS = ["server:mcp:agent-memory", "server:mcp:lab-docs"]
# Two Lab Recall presets, picked per chat in the model menu (owner, 2026-11-19: "Can we make it toggle-able?"). Same
# tools, prompt and native tool calls; only the model differs. Measured on the real model and tools, 5 runs per question
# (docs/runbooks/shared-agent-memory.md § the Lab Recall preset): qwen2.5:7b-operator 4-15 s, right on recorded topics,
# but invented a meaning for an unrecorded term about half the time; qwen3:30b-a3b 60-120 s (half on the CPU), 10/10.
LAB_RECALLS = {
    "lab-recall": {
        "name": "Lab Recall", "base": "qwen2.5:7b-operator",
        "description": "Fast (seconds): the lab's memory and docs. Can guess at a term it does not find, so check the note "
                       "it names; for a careful answer use Lab Recall (thorough)."},
    "lab-recall-thorough": {
        "name": "Lab Recall (thorough)", "base": "qwen3:30b-a3b",
        "description": "Careful (about a minute): the lab's memory and docs, checked before it answers; says plainly when "
                       "a term is not recorded."},
}
# B250 (2026-11-19): asked "How does Weyland manage ADRs?", Lab Recall (memory only) found no note and expanded ADR as
# "Actionable Design Reviews". This prompt was chosen by measurement on the real model and tools (qwen2.5:7b-operator,
# native tool calls, 5 runs per question): the first loose prompt scored 1/10 (it skipped reading, trusted any
# search hit, and invented "Quality Zone Reports"); forcing the read alone made it claim the top note mentioned the
# term; reading AND gating each source on the asked term appearing in it scored 10/10, twice.
LAB_RECALL_SYSTEM = (
    "You answer questions about the weyland lab from its own records. Do these steps in order, every time:\n"
    "1. Call agent-memory_search_notes with the user's question.\n"
    "2. Call agent-memory_read_note on the first result.\n"
    "3. Check the note you read: does it contain the term the user asked about (singular or plural, for example "
    "\"ADR\" or \"ADRs\")? If yes, answer from that note. If no, ignore that note and call "
    "lab-docs_context_context_search with the question.\n"
    "4. Check the docs results the same way. If no note or document you read contains the term, reply only that you "
    "could not find it, for example: \"I could not find XYZ in the lab's memory or docs.\" and stop.\n"
    "Rules: answer only with facts written in what you read, and name the note or file. Never claim a note says "
    "something it does not say. If the text you read spells out an acronym, copy that spelling exactly; if it does "
    "not, do not expand the acronym at all. If a tool fails, say which source could not be reached. For the lab's "
    "current state (what is running, failing or alerting), point to the Lab Status model."
)
LAB_STATUS_SYSTEM = (
    "You answer questions about the weyland lab's current state: what is running, what is failing, what is alerting, "
    "and what the metrics and logs show. Use the Lab fleet tools to look; answer only from what they returned, name "
    "the tool you used, and say plainly when a tool failed or returned nothing. "
    "Alerts: query Prometheus with lab-fleet_grafana_query_prometheus, datasourceUid \"prometheus\", queryType "
    "\"instant\", endTime \"now\", expr 'ALERTS{alertstate=\"firing\"}'. The alert named Watchdog always fires by "
    "design (it proves alerting works); never report it as a problem. Logs: lab-fleet_grafana_query_loki_logs with "
    "datasourceUid \"loki\". "
    "The tools are read-only and so are you: never present a command that changes the cluster (delete, scale, "
    "restart, apply, patch) as something to run. If a fix needs a change, describe it and say the owner makes changes "
    "through git."
)


class CurateError(Exception):
    """The live state cannot be curated safely (e.g. the guarded lane is missing)."""


# ---- pure functions: the curated state, computed from the live one -------------------------------------------------

def desired_openai(cur):
    urls = cur.get("OPENAI_API_BASE_URLS") or []
    if NEMO_URL not in urls:
        raise CurateError(f"no nemo-guardrails connection ({NEMO_URL}) in the live OpenAI config; refusing to apply")
    i = urls.index(NEMO_URL)
    keys = cur.get("OPENAI_API_KEYS") or []
    return {"ENABLE_OPENAI_API": True, "OPENAI_API_BASE_URLS": [NEMO_URL],
            "OPENAI_API_KEYS": [keys[i] if i < len(keys) else ""],
            "OPENAI_API_CONFIGS": {"0": (cur.get("OPENAI_API_CONFIGS") or {}).get(str(i), {})}}


def desired_admin_config(cur):
    out = {k: v for k, v in cur.items() if k not in MFA_FIELDS}
    out["ENABLE_COMMUNITY_SHARING"] = False
    return out


def fleet_connection():
    return {"url": f"{GATEWAY}/mcp-fleet", "path": "", "type": "mcp", "auth_type": "system_oauth",
            "forward_cookies": False, "headers": None, "key": "",
            "config": {"enable": True, "function_name_filter_list": ",".join(FLEET_TOOLS), "access_grants": []},
            "info": {"id": "lab-fleet", "name": "Lab fleet",
                     "description": "Read-only lab status: Kubernetes, alerts, metrics, logs, catalog, RAG search — as you (B116)"},
            "spec_type": "url", "spec": ""}


def docs_connection():
    """Lab Recall's docs corpus (B250, 2026-11-19): the same /mcp-fleet gateway, as the signed-in person, allowlisted to
    the ONE docs-search tool, so Lab Recall can read the docs (and docs/adr/) but not the live-status tools."""
    return {**fleet_connection(),
            "config": {"enable": True, "function_name_filter_list": DOCS_TOOL, "access_grants": []},
            "info": {"id": "lab-docs", "name": "Lab docs",
                     "description": "Search the lab's docs, runbooks and decision records (docs/adr/) — as you (B250)"}}


def desired_tool_servers(cur):
    return ([c for c in cur if (c.get("info") or {}).get("id") not in ("lab-fleet", "lab-docs")]
            + [fleet_connection(), docs_connection()])


def desired_models_config(cur):
    return {**cur, "DEFAULT_MODELS": "lab-recall", "MODEL_ORDER_LIST": MODEL_ORDER,
            "DEFAULT_MODEL_PARAMS": {**(cur.get("DEFAULT_MODEL_PARAMS") or {}), "num_ctx": NUM_CTX}}


def desired_lab_recall(cur, rid="lab-recall"):
    """One Lab Recall preset (LAB_RECALLS[rid]); an existing entry keeps its other fields, grants and tags."""
    spec = LAB_RECALLS[rid]
    cur = dict(cur or {})
    meta = dict(cur.get("meta") or {})
    caps = dict(meta.get("capabilities") or {})
    caps.update(dict.fromkeys(LAB_RECALL_OFF, False), builtin_tools=False)
    return {**cur, "id": rid, "name": spec["name"], "base_model_id": spec["base"], "is_active": True,
            "params": {**(cur.get("params") or {}), "system": LAB_RECALL_SYSTEM, "function_calling": "native"},
            "meta": {**meta, "capabilities": caps, "toolIds": LAB_RECALL_TOOLS, "description": spec["description"]},
            "access_grants": cur.get("access_grants") or PUBLIC_READ}


def lab_recall_ok(entry, rid="lab-recall"):
    entry = entry or {}
    return (entry.get("base_model_id") == LAB_RECALLS[rid]["base"] and _meta(entry).get("toolIds") == LAB_RECALL_TOOLS
            and (entry.get("params") or {}).get("system") == LAB_RECALL_SYSTEM
            and (entry.get("params") or {}).get("function_calling") == "native")


def desired_lab_status(base_caps):
    return {
        "id": "lab-status", "name": "Lab Status", "base_model_id": LAB_STATUS_BASE, "is_active": True,
        "params": {"system": LAB_STATUS_SYSTEM},
        "meta": {"description": "Live lab status from the read-only fleet tools (Kubernetes, alerts, metrics, logs, "
                                "catalog), as you.",
                 "toolIds": ["server:mcp:lab-fleet"], "capabilities": {**base_caps, "builtin_tools": False},
                 "suggestion_prompts": [{"content": "Are any alerts firing right now?"},
                                        {"content": "Which pods in the weyland namespace are not healthy?"},
                                        {"content": "What are the busiest pods on mother by CPU and memory?"}],
                 "tags": [], "knowledge": []},
        "access_grants": [{"principal_type": "user", "principal_id": "*", "permission": "read"}],
    }


def hidden_entry(model_id, existing, name):
    if existing:
        return {**existing, "meta": {**(existing.get("meta") or {}), "hidden": True}}
    return {"id": model_id, "name": name, "base_model_id": None, "meta": {"hidden": True}, "params": {},
            "access_grants": [], "is_active": True}


def desired_guarded_chat(existing):
    """The guarded lane's model entry: its name and description; existing meta and grants kept, public read if none."""
    e = existing or {"id": GUARDED_ID, "base_model_id": None, "params": {}, "is_active": True}
    return {**e, "name": GUARDED_NAME, "meta": {**(e.get("meta") or {}), "description": GUARDED_DESCRIPTION},
            "access_grants": e.get("access_grants") or PUBLIC_READ}


def guarded_chat_ok(entry):
    return bool(entry) and entry.get("name") == GUARDED_NAME


def desired_audio(cur):
    """STT at the lab's whisper and TTS at the lab's Kokoro (both OpenAI engine); every other field as it is.
    `realtime` is optional in 0.12's update form, so it is never resent (an omitted block is left alone)."""
    stt = {**cur["stt"], "ENGINE": "openai", "MODEL": "whisper-1", "OPENAI_API_BASE_URL": WHISPER_URL,
           "OPENAI_API_KEY": cur["stt"].get("OPENAI_API_KEY") or "sk-local-whisper"}   # the shim ignores the key
    tts = {**cur["tts"], "ENGINE": "openai", "MODEL": "kokoro", "VOICE": KOKORO_VOICE, "OPENAI_API_BASE_URL": KOKORO_URL,
           "OPENAI_API_KEY": cur["tts"].get("OPENAI_API_KEY") or "sk-local-kokoro"}    # Kokoro ignores the key
    return {"tts": tts, "stt": stt}


def stt_ok(cur):
    stt = cur.get("stt") or {}
    return stt.get("ENGINE") == "openai" and stt.get("OPENAI_API_BASE_URL") == WHISPER_URL


def tts_ok(cur):
    tts = cur.get("tts") or {}
    return (tts.get("ENGINE") == "openai" and tts.get("OPENAI_API_BASE_URL") == KOKORO_URL
            and tts.get("MODEL") == "kokoro" and tts.get("VOICE") == KOKORO_VOICE)


def drift(want, have):
    """Top-level keys of `want` whose value differs in `have` (extra keys in `have` are fine)."""
    return [k for k, v in want.items() if have.get(k) != v]


# ---- I/O ---------------------------------------------------------------------------------------------------------

class Client:
    def __init__(self, base, key):
        self.base, self.key = base.rstrip("/"), key

    def call(self, method, path, body=None):
        req = urllib.request.Request(self.base + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            raise CurateError(f"{method} {path}: HTTP {e.code} {e.read()[:300]!r}") from None


def _items(resp):
    return resp.get("items", resp) if isinstance(resp, dict) else resp


def _meta(model):
    return (model or {}).get("meta") or {}


def _check_models(all_models, mc):
    out = [(f"hidden: {mid}", _meta(all_models.get(mid)).get("hidden") is True) for mid in HIDDEN_MODELS]
    want_mc = desired_models_config(mc)
    off = drift({k: want_mc[k] for k in ("DEFAULT_MODELS", "MODEL_ORDER_LIST", "DEFAULT_MODEL_PARAMS")}, mc)
    out += [(f"models config: {k}", False) for k in off] or [
        ("models config: default Lab Recall, picker order, num_ctx 16384", True)]
    caps = _meta(all_models.get("lab-recall")).get("capabilities") or {}
    out.append(("Lab Recall: web search / image generation / terminal off",
                all(caps.get(x) is False for x in LAB_RECALL_OFF)))
    for rid, spec in LAB_RECALLS.items():
        out.append((f"{spec['name']}: {spec['base']}, native tools agent-memory + lab-docs, recall prompt",
                    lab_recall_ok(all_models.get(rid), rid)))
    out.append((f"guarded chat named '{GUARDED_NAME}'", guarded_chat_ok(all_models.get(GUARDED_ID))))
    ls = all_models.get("lab-status") or {}
    params = ls.get("params") or {}
    out.append(("Lab Status preset (qwen3:30b-a3b, fleet tools, prompt)",
                ls.get("base_model_id") == LAB_STATUS_BASE and params.get("system") == LAB_STATUS_SYSTEM
                and "think" not in params and _meta(ls).get("toolIds") == ["server:mcp:lab-fleet"]))
    return out


def _check_tool_servers(conns):
    by_id = {(x.get("info") or {}).get("id"): x for x in conns}
    fleet = by_id.get("lab-fleet") or {}
    docs = by_id.get("lab-docs") or {}
    allow = (fleet.get("config") or {}).get("function_name_filter_list", "").split(",")
    return [("tool server agent-memory present", "agent-memory" in by_id),
            ("tool server lab-fleet = /mcp-fleet, system_oauth, 13-tool allowlist",
             fleet.get("url") == f"{GATEWAY}/mcp-fleet" and fleet.get("auth_type") == "system_oauth"
             and allow == FLEET_TOOLS),
            ("tool server lab-docs = /mcp-fleet, system_oauth, docs search only",
             docs.get("url") == f"{GATEWAY}/mcp-fleet" and docs.get("auth_type") == "system_oauth"
             and (docs.get("config") or {}).get("function_name_filter_list") == DOCS_TOOL)]


def check(c):
    """One (label, ok) pair per curated setting, read from the live app."""
    out = [("OpenAI connections = nemo-guardrails only",
            c.call("GET", "/openai/config")["OPENAI_API_BASE_URLS"] == [NEMO_URL]),
           ("community sharing off", c.call("GET", ADMIN_CONFIG)["ENABLE_COMMUNITY_SHARING"] is False),
           ("Arena model off",
            c.call("GET", "/api/v1/evaluations/config")["ENABLE_EVALUATION_ARENA_MODELS"] is False)]
    all_models = {m["id"]: m for m in c.call("GET", "/api/v1/models/all")}  # /models/list returns presets only
    out += _check_models(all_models, c.call("GET", MODELS_CONFIG))
    out += _check_tool_servers(c.call("GET", TOOL_SERVERS)["TOOL_SERVER_CONNECTIONS"])
    audio = c.call("GET", AUDIO_CONFIG)
    out.append(("speech-to-text = OpenAI engine at the in-cluster whisper (timberback)", stt_ok(audio)))
    out.append((f"text-to-speech = OpenAI engine at the in-cluster Kokoro, voice {KOKORO_VOICE}", tts_ok(audio)))
    return out


def apply(c):
    c.call("POST", "/openai/config/update", desired_openai(c.call("GET", "/openai/config")))
    c.call("POST", ADMIN_CONFIG, desired_admin_config(c.call("GET", ADMIN_CONFIG)))
    c.call("POST", "/api/v1/evaluations/config", {"ENABLE_EVALUATION_ARENA_MODELS": False, "EVALUATION_ARENA_MODELS": []})
    all_models = {m["id"]: m for m in c.call("GET", "/api/v1/models/all")}
    names = {m["id"]: m.get("name", m["id"]) for m in c.call("GET", "/api/models")["data"]}
    for mid in HIDDEN_MODELS:
        entry = hidden_entry(mid, all_models.get(mid), names.get(mid, mid))
        c.call("POST", MODEL_UPDATE if mid in all_models else MODEL_CREATE, entry)
    c.call("POST", TOOL_SERVERS,
           {"TOOL_SERVER_CONNECTIONS": desired_tool_servers(c.call("GET", TOOL_SERVERS)["TOOL_SERVER_CONNECTIONS"])})
    lr = c.call("GET", "/api/v1/models/model?id=lab-recall")
    for rid in LAB_RECALLS:
        c.call("POST", MODEL_UPDATE if rid in all_models else MODEL_CREATE,
               desired_lab_recall(all_models.get(rid), rid))
    ls = desired_lab_status((lr.get("meta") or {}).get("capabilities") or {})
    c.call("POST", MODEL_UPDATE if "lab-status" in all_models else MODEL_CREATE, ls)
    c.call("POST", MODEL_UPDATE if GUARDED_ID in all_models else MODEL_CREATE,
           desired_guarded_chat(all_models.get(GUARDED_ID)))
    c.call("POST", MODELS_CONFIG, desired_models_config(c.call("GET", MODELS_CONFIG)))
    c.call("POST", AUDIO_CONFIG + "/update", desired_audio(c.call("GET", AUDIO_CONFIG)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="read only: report drift, exit 1 on any")
    args = ap.parse_args(argv)
    key = os.environ.get("OPEN_WEBUI_API_KEY")
    if not key:
        print("OPEN_WEBUI_API_KEY is not set (scripts/.env)", file=sys.stderr)
        return 2
    c = Client(os.environ.get("OPEN_WEBUI_URL", "https://chat.weyland.lab"), key)
    try:
        if not args.check:
            apply(c)
        results = check(c)
    except CurateError as e:
        print(f"FAIL {e}", file=sys.stderr)
        return 2
    for label, ok in results:
        print(f"{'OK   ' if ok else 'DRIFT'} {label}")
    bad = sum(1 for _, ok in results if not ok)
    print(f"{'curated' if not bad else f'{bad} setting(s) drifted'} ({len(results)} checked)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
