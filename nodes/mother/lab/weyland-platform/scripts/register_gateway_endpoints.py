#!/usr/bin/env python3
"""B100 P4 — codify the MLflow AI Gateway endpoints (idempotent).

The built-in AI Gateway (MLflow 3.11+, mlflow.weyland.lab) is DB-backed + UI-configured — which doesn't fit our
GitOps-everything setup. This script is the codified source of truth: it (re)creates the gateway's secrets,
model-definitions, and endpoints via the REST API (/api/3.0/mlflow/gateway/...), idempotently — so the endpoint set
lives in git and survives an MLflow DB reset instead of being click-ops. Mirrors scripts/register_prompts.py (B100 P2).

The 3-step chain (discovered from the running server's handlers + proto schema):
  secret  {secret_name, provider, secret_value:{api_key}, auth_config:{api_base, auth_mode}}
    -> model-definition {name, secret_id, provider, model_name}
      -> endpoint {name, model_configs:[{model_definition_id, linkage_type, weight}], usage_tracking}
NB: the OpenAI-compat base URL lives on the SECRET's auth_config.api_base, and MUST include /v1 (the provider appends
/chat/completions; a bare host 404s from Ollama).

Run from rogueone. Provider keys + the gateway URL live in the gitignored TOP-LEVEL `scripts/.env` (repo root; see
scripts/.env.example) — the script AUTO-LOADS it (walks up to <repo>/scripts/.env), so there's no sourcing and no
navigating the nodes/ tree. The gateway is reached via the mlflow-lan LAN NodePort (http://192.168.1.243:30500,
source-pinned to rogueone) — no port-forward, and no forward-auth (unlike the mlflow.weyland.lab ingress). Run:
  python3 nodes/mother/lab/weyland-platform/scripts/register_gateway_endpoints.py
"""
import json
import os
import pathlib
import urllib.request as u


def _load_dotenv():
    """Auto-load the top-level scripts/.env (gitignored) so keys never hit the CLI/repo/chat and you don't navigate
    the nodes/ maze. Walks up from this file to the first <ancestor>/scripts/.env. Real process env always wins."""
    try:
        cands = [os.environ.get("WEYLAND_ENV_FILE")] + \
                [a / "scripts" / ".env" for a in pathlib.Path(__file__).resolve().parents]
    except NameError:
        cands = [os.environ.get("WEYLAND_ENV_FILE"), pathlib.Path.cwd() / "scripts" / ".env", pathlib.Path.cwd() / ".env"]
    for c in cands:
        if c and pathlib.Path(c).is_file():
            for ln in pathlib.Path(c).read_text().splitlines():
                ln = ln.strip()
                if not ln or ln.startswith("#"):
                    continue
                ln = ln[7:].lstrip() if ln.startswith("export ") else ln
                if "=" in ln:
                    k, v = ln.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            print(f"loaded env from {c}")
            return
    print("no scripts/.env found — using process env only")


_load_dotenv()

GW = os.environ.get("MLFLOW_GATEWAY_API", "http://192.168.1.243:30500") + "/api/3.0/mlflow/gateway"  # mlflow-lan NodePort (rogueone)

# One shared secret per provider. Ollama ignores the api_key, but the field is required -> a dummy.
OLLAMA_BASE = os.environ.get("OLLAMA_OPENAI_BASE", "http://192.168.1.230:11434/v1")  # /v1 is required
SECRETS = [
    {"secret_name": "ollama-local", "provider": "ollama", "api_key": "ollama", "api_base": OLLAMA_BASE},
]
# endpoint name -> (provider, secret_name, model_name). The 6 local models, unified behind the gateway.
ENDPOINTS = [
    ("ollama-gpt-oss-20b",        "ollama", "ollama-local", "gpt-oss:20b"),
    ("ollama-qwen3-14b",          "ollama", "ollama-local", "qwen3:14b"),
    ("ollama-qwen3-30b-a3b",      "ollama", "ollama-local", "qwen3:30b-a3b"),
    ("ollama-mistral-small-24b",  "ollama", "ollama-local", "mistral-small3.2:24b"),
    ("ollama-qwen3-coder-30b",    "ollama", "ollama-local", "qwen3-coder:30b"),
    ("ollama-deepseek-coder-16b", "ollama", "ollama-local", "deepseek-coder-v2:16b"),
    ("ollama-llama32-3b",         "ollama", "ollama-local", "llama3.2:3b"),  # small/fast (over-eager as a guard judge)
    ("ollama-qwen25-7b",          "ollama", "ollama-local", "qwen2.5:7b"),   # the guard + eval judge (stronger JSON/judgment)
]
# --- Category B/C (add when keyed, then re-run — idempotent) ---
# NEVER hardcode a key here (this repo is PUBLIC). Keys come from the gitignored .env (see .env.example): put the
# ones you have there (e.g. OPENAI_API_KEY=...) and re-run. Each provider is gated on its env var.
# Native cloud providers need NO api_base (the gateway knows their endpoints); Ollama/LiteLLM/Groq-via-openai do.
# Model lists are env-overridable (comma-sep) with sensible defaults.
_NATIVE = [
    # (env_var, secret_name, provider, default_models)
    ("OPENAI_API_KEY",     "openai",     "openai",     "gpt-5-mini"),
    ("ANTHROPIC_API_KEY",  "anthropic",  "anthropic",  "claude-haiku-4-5"),
    ("GEMINI_API_KEY",     "gemini",     "gemini",     "gemini-2.5-flash"),
    ("MISTRAL_API_KEY",    "mistral",    "mistral",    "mistral-small-latest"),
    ("COHERE_API_KEY",     "cohere",     "cohere",     "command-r"),
    ("DEEPSEEK_API_KEY",   "deepseek",   "deepseek",   "deepseek-chat"),
    ("TOGETHER_API_KEY",   "together",   "togetherai", "meta-llama/Llama-3.3-70B-Instruct-Turbo"),
    ("OPENROUTER_API_KEY", "openrouter", "openrouter", "meta-llama/llama-3.3-70b-instruct:free"),
    ("XAI_API_KEY",        "xai",        "xai",        "grok-3-mini"),
]
for env_var, secret_name, provider, default_models in _NATIVE:
    key = os.environ.get(env_var)
    if not key:
        continue
    SECRETS.append({"secret_name": secret_name, "provider": provider, "api_key": key})  # no api_base — native
    models = os.environ.get(f"{secret_name.upper()}_MODELS", default_models)
    for mn in [m for m in models.split(",") if m.strip()]:
        slug = mn.strip().replace("/", "-").replace(":", "-").replace(".", "-")
        ENDPOINTS.append((f"{secret_name}-{slug}", provider, secret_name, mn.strip()))

# LiteLLM (B26 — its Gemini/OpenRouter + spend meter) as an openai-compat backend (needs api_base):
if os.environ.get("LITELLM_API_KEY"):
    SECRETS.append({"secret_name": "litellm", "provider": "openai", "api_key": os.environ["LITELLM_API_KEY"],
                    "api_base": os.environ.get("LITELLM_BASE", "http://litellm.weyland.svc.cluster.local:4000/v1")})
    for mn in [m for m in os.environ.get("LITELLM_MODELS", "").split(",") if m.strip()]:
        ENDPOINTS.append((f"litellm-{mn.strip().replace('/', '-').replace(':', '-')}", "openai", "litellm", mn.strip()))


def _req(method, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = u.Request(GW + path, data=data, method=method,
                    headers={"Content-Type": "application/json"} if data else {})
    try:
        with u.urlopen(req, timeout=30) as resp:
            body = resp.read()
            return json.loads(body) if body else {}
    except u.HTTPError as e:
        raise RuntimeError(f"{method} {path} -> {e.code}: {e.read()[:400].decode(errors='replace')}") from None


def _list(path):
    """Return the first list value in the response dict (robust to the exact key name)."""
    for v in _req("GET", path).values():
        if isinstance(v, list):
            return v
    return []


def ensure_secret(spec):
    def find():
        return next((s["secret_id"] for s in _list("/secrets/list") if s["secret_name"] == spec["secret_name"]), None)
    if (sid := find()):
        return sid
    auth_config = {"auth_mode": "api_key"}
    if spec.get("api_base"):  # only Ollama/LiteLLM/Groq-via-openai; native cloud providers use their default endpoint
        auth_config["api_base"] = spec["api_base"]
    _req("POST", "/secrets/create", {
        "secret_name": spec["secret_name"], "provider": spec["provider"],
        "secret_value": {"api_key": spec["api_key"]},
        "auth_config": auth_config,
    })
    if (sid := find()):
        return sid
    raise RuntimeError(f"secret {spec['secret_name']} missing after create")


def ensure_model_def(name, secret_id, provider, model_name):
    def find():
        return next((d["model_definition_id"] for d in _list("/model-definitions/list") if d["name"] == name), None)
    if (mid := find()):
        return mid
    _req("POST", "/model-definitions/create",
         {"name": name, "secret_id": secret_id, "provider": provider, "model_name": model_name})
    if (mid := find()):
        return mid
    raise RuntimeError(f"model-definition {name} missing after create")


# Guardrails are created in the UI (each references an mlflow.genai scorer — durable in Postgres). This script does
# NOT recreate them; it ATTACHES the existing ones (by name) to every endpoint EXCEPT the judge endpoints — guarding
# a judge recurses (guardrail -> judge -> the judge's own guardrail -> ...). Idempotent: skips already-bound pairs.
GUARD_NAMES = [n.strip() for n in os.environ.get("GATEWAY_GUARDRAILS", "Safety,PII Detection").split(",") if n.strip()]
JUDGE_ENDPOINTS = {x.strip() for x in os.environ.get("GATEWAY_JUDGE_ENDPOINTS", "ollama-qwen25-7b").split(",") if x.strip()}
# NOTE (B15): a guard-exemption for coding endpoints was trialled here so coding TUIs could stream through the gateway.
# It was reverted — agentic coding via the gateway proved unworkable (hosted multi-turn tool loops crash MLflow; local
# 16GB models are poor agents regardless). Coding agents point DIRECTLY at the provider instead. See runbooks/coding-agents.md.


def _list_for(endpoint_id):
    from urllib.parse import quote
    d = _req("GET", f"/guardrails/list-for-endpoint?endpoint_id={quote(endpoint_id)}")  # GET + query param
    for v in d.values():
        if isinstance(v, list):
            return v
    return []


def attach_guardrails():
    guards = {g["name"]: g["guardrail_id"] for g in _list("/guardrails/list")}
    want = [(n, guards[n]) for n in GUARD_NAMES if n in guards]
    if not want:
        print(f"guardrails: none of {GUARD_NAMES} exist yet (create them in the UI) — skipping attach")
        return
    attached = 0
    for e in _list("/endpoints/list"):
        if e["name"] in JUDGE_ENDPOINTS:
            print(f"  skip (judge, left unguarded to avoid recursion): {e['name']}")
            continue
        bound = {c.get("guardrail_id") for c in _list_for(e["endpoint_id"])}
        for gname, gid in want:
            if gid in bound:
                continue
            try:
                _req("POST", "/guardrails/add-to-endpoint", {"endpoint_id": e["endpoint_id"], "guardrail_id": gid})
                print(f"  attached {gname} -> {e['name']}")
                attached += 1
            except RuntimeError as exc:
                print(f"  attach {gname} -> {e['name']} FAILED: {exc}")
    print(f"guardrails: {attached} new attachment(s) ({len(want)} guardrail(s), judges excluded: {sorted(JUDGE_ENDPOINTS)})")


def _judge_endpoint_id():
    judge_name = next(iter(JUDGE_ENDPOINTS), None)
    return next((e["endpoint_id"] for e in _list("/endpoints/list") if e["name"] == judge_name), None)


def prune_stale_guardrails():
    """Delete guardrails whose judge model is NOT the current judge endpoint (left over from a judge swap) so the
    name-based attach isn't ambiguous. Detaches from every endpoint first, then deletes the guardrail."""
    judge_id = _judge_endpoint_id()
    if not judge_id:
        print("prune: judge endpoint not found — skipping")
        return
    endpoint_ids = [e["endpoint_id"] for e in _list("/endpoints/list")]
    for g in _list("/guardrails/list"):
        try:
            model = json.loads(g["scorer"]["serialized_scorer"])["instructions_judge_pydantic_data"].get("model", "")
        except Exception:
            model = ""
        if model.endswith(judge_id):   # judged by the current judge -> keep
            continue
        gid = g["guardrail_id"]
        for eid in endpoint_ids:
            try:
                _req("DELETE", "/guardrails/remove-from-endpoint", {"endpoint_id": eid, "guardrail_id": gid})
            except RuntimeError:
                pass  # not attached to that endpoint
        _req("DELETE", "/guardrails/delete", {"guardrail_id": gid})
        print(f"  pruned stale guardrail {g['name']} ({gid}) — old judge {model}")


# Guardrail definitions — fully scriptable (scorers/register -> guardrails/create). Instructions are verbatim from
# the MLflow UI defaults so behavior matches. Judge = the current JUDGE endpoint; idempotent by guardrail name.
_SAFETY_INSTR = """You are a content-safety classifier. Decide whether the text below violates policies against hate speech, harassment, incitement of violence, or the promotion of illegal or severely harmful acts. Tool calls, code, logs, SQL, and structured/config data are normal and SAFE unless they clearly contain such content.

Output ONLY a single raw JSON object — no markdown, no code fences, no text before or after it — in exactly this form:
{"result": "yes", "rationale": "one short sentence"}

Set "result" to exactly "yes" when the text is SAFE (no violation), or exactly "no" when it violates policy. The "result" value MUST be the literal string "yes" or "no" and nothing else.

<text>{{ outputs }}</text>"""

_PII_INSTR = """You are a PII detector. Decide whether the text below contains personal data that could identify a real individual — real personal names, emails, phone numbers, home addresses, government IDs, credit-card numbers, or dates of birth. Service names, hostnames, Kubernetes identifiers, internal IPs, and technical config are NOT PII.

Output ONLY a single raw JSON object — no markdown, no code fences, no text before or after it — in exactly this form:
{"result": "yes", "rationale": "one short sentence"}

Set "result" to exactly "yes" when the text contains NO PII, or exactly "no" when PII is present. The "result" value MUST be the literal string "yes" or "no" and nothing else.

<text>{{ inputs }}</text>"""

# (guardrail_name, scorer_name, instructions, stage, action, needs_action_endpoint)
GUARD_DEFS = [
    ("Safety",        "safety",        _SAFETY_INSTR, "AFTER",  "VALIDATION",   False),
    ("PII Detection", "pii detection", _PII_INSTR,    "BEFORE", "SANITIZATION", True),
]


def ensure_guardrails():
    """Create the Safety + PII guardrails judged by the current JUDGE endpoint if they don't already exist."""
    judge_id = _judge_endpoint_id()
    if not judge_id:
        print("ensure_guardrails: judge endpoint missing — skipping")
        return
    judge_name = next(iter(JUDGE_ENDPOINTS))
    api = GW.rsplit("/gateway", 1)[0]  # .../api/3.0/mlflow (scorers live outside the gateway namespace)
    existing = {g["name"] for g in _list("/guardrails/list")}
    for gname, scorer_name, instr, stage, action, needs_ep in GUARD_DEFS:
        if gname in existing:
            print(f"  guardrail exists: {gname}")
            continue
        serialized = json.dumps({"name": scorer_name, "instructions_judge_pydantic_data": {
            "instructions": instr, "feedback_value_type": {"type": "string", "enum": ["yes", "no"]},
            "model": f"gateway:/{judge_name}"}})  # register resolves by endpoint NAME (stores the id form)
        req = u.Request(api + "/scorers/register", method="POST", headers={"Content-Type": "application/json"},
                        data=json.dumps({"experiment_id": "0", "name": scorer_name, "serialized_scorer": serialized}).encode())
        try:
            with u.urlopen(req, timeout=30) as r:
                reg = json.loads(r.read())
        except u.HTTPError as e:
            raise RuntimeError(f"scorers/register {scorer_name} -> {e.code}: {e.read()[:400].decode(errors='replace')}") from None
        payload = {"name": gname, "scorer_id": reg["scorer_id"], "scorer_version": reg["version"],
                   "stage": stage, "action": action}
        if needs_ep:
            payload["action_endpoint_id"] = judge_id  # FK to endpoints.endpoint_id (the id, not the name)
        _req("POST", "/guardrails/create", payload)
        print(f"  created guardrail: {gname} (judge={judge_name}, {stage}/{action})")


# Budget: a GLOBAL spend cap (budgets are workspace/global-scoped — there's no per-endpoint field). Caps total paid
# spend (OpenAI/Anthropic/xAI) against a runaway loop. REJECT = hard-block once exceeded; ALERT = warn only.
BUDGET_USD = float(os.environ.get("GATEWAY_BUDGET_USD", "10"))
BUDGET_MONTHS = int(os.environ.get("GATEWAY_BUDGET_MONTHS", "1"))
BUDGET_ACTION = os.environ.get("GATEWAY_BUDGET_ACTION", "REJECT")  # REJECT (hard cap) | ALERT (warn only)


def ensure_budget():
    if BUDGET_USD <= 0 or _list("/budgets/list"):
        print("  budget: exists or disabled — skipping")
        return
    _req("POST", "/budgets/create", {
        "budget_unit": "USD", "budget_amount": BUDGET_USD,
        "duration": {"unit": "MONTHS", "value": BUDGET_MONTHS},
        "target_scope": "GLOBAL", "budget_action": BUDGET_ACTION,
    })
    print(f"  created GLOBAL budget: ${BUDGET_USD:g} per {BUDGET_MONTHS}mo, action={BUDGET_ACTION}")


def prune_orphan_endpoints():
    """Opt-in (GATEWAY_PRUNE_ORPHANS=1): delete endpoints no longer in the config — a key removed from .env, or a
    model changed (the endpoint name embeds the model slug, so a new model = a new name + an orphaned old one). This
    is how you TRIM a dead provider (e.g. no-credit deepseek): drop its key from scripts/.env, re-run with the flag.
    Never touches the judges. Detaches guardrails first."""
    if os.environ.get("GATEWAY_PRUNE_ORPHANS") != "1":
        return
    keep = {ep[0] for ep in ENDPOINTS} | set(JUDGE_ENDPOINTS)
    for e in _list("/endpoints/list"):
        if e["name"] in keep:
            continue
        eid = e["endpoint_id"]
        for g in _list("/guardrails/list"):
            try:
                _req("DELETE", "/guardrails/remove-from-endpoint", {"endpoint_id": eid, "guardrail_id": g["guardrail_id"]})
            except RuntimeError:
                pass
        _req("DELETE", "/endpoints/delete", {"endpoint_id": eid})
        print(f"  pruned orphan endpoint: {e['name']}")


def refresh_guardrails():
    """Opt-in (REFRESH_GUARDRAILS=1): delete the GUARD_DEFS guardrails so ensure_guardrails() recreates them with the
    CURRENT instructions. Guardrails are otherwise idempotent by NAME, so an instruction edit is a silent no-op —
    run with this flag after editing _SAFETY_INSTR / _PII_INSTR. Detaches from every endpoint first, then deletes."""
    if os.environ.get("REFRESH_GUARDRAILS") != "1":
        return
    names = {gname for gname, *_ in GUARD_DEFS}
    endpoint_ids = [e["endpoint_id"] for e in _list("/endpoints/list")]
    for g in _list("/guardrails/list"):
        if g["name"] not in names:
            continue
        gid = g["guardrail_id"]
        for eid in endpoint_ids:
            try:
                _req("DELETE", "/guardrails/remove-from-endpoint", {"endpoint_id": eid, "guardrail_id": gid})
            except RuntimeError:
                pass
        _req("DELETE", "/guardrails/delete", {"guardrail_id": gid})
        print(f"  refreshed (deleted for recreate with new instructions): {g['name']} ({gid})")


def main():
    sids = {s["secret_name"]: ensure_secret(s) for s in SECRETS}
    print(f"secrets: {sids}")
    existing = {e["name"] for e in _list("/endpoints/list")}
    created = skipped = 0
    for ep_name, provider, secret_name, model_name in ENDPOINTS:
        if ep_name in existing:
            print(f"  skip (exists): {ep_name}")
            skipped += 1
            continue
        mdid = ensure_model_def(f"{ep_name}-md", sids[secret_name], provider, model_name)
        _req("POST", "/endpoints/create", {
            "name": ep_name,
            "model_configs": [{"model_definition_id": mdid, "linkage_type": "PRIMARY", "weight": 1.0}],
            "usage_tracking": True,
        })
        print(f"  created: {ep_name} -> {model_name}")
        created += 1
    print(f"done: {created} created, {skipped} skipped, {len(ENDPOINTS)} total endpoints")
    prune_orphan_endpoints()
    prune_stale_guardrails()
    refresh_guardrails()   # REFRESH_GUARDRAILS=1 → recreate Safety/PII with the current instructions
    ensure_guardrails()
    attach_guardrails()
    ensure_budget()


if __name__ == "__main__":
    main()
