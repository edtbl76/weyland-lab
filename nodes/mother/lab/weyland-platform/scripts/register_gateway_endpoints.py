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

Run from anywhere. Provider keys + the gateway URL live in the gitignored TOP-LEVEL `scripts/.env` (repo root; see
scripts/.env.example) — the script AUTO-LOADS it (walks up to <repo>/scripts/.env), so there's no sourcing and no
navigating the nodes/ tree. Port-forward the `mlflow` service :5000 to localhost first (the gateway API has no auth
at the pod level), then:
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

GW = os.environ.get("MLFLOW_GATEWAY_API", "http://localhost:5000") + "/api/3.0/mlflow/gateway"

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


if __name__ == "__main__":
    main()
