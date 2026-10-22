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

# One shared secret per provider. Ollama itself ignores the api_key; since B211 (2026-10-22) rogueone's front door checks
# it, so it is the front-door token from scripts/.env (OLLAMA_PROXY_TOKEN). The value is never printed.
OLLAMA_BASE = os.environ.get("OLLAMA_OPENAI_BASE", "http://192.168.1.230:11434/v1")  # /v1 is required
SECRETS = [
    {"secret_name": "ollama-local", "provider": "ollama", "api_key": os.environ.get("OLLAMA_PROXY_TOKEN", "ollama"),
     "api_base": OLLAMA_BASE},
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
    ("ollama-qwen25-7b",          "ollama", "ollama-local", "qwen2.5:7b"),   # judge until B215 (blocked contact details)
    # THE judge (guards + eval panel, B215): its own endpoint so it stays unguarded while ollama-qwen3-14b keeps its guards.
    ("ollama-qwen3-14b-judge",    "ollama", "ollama-local", "qwen3:14b"),
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
# PER-CONSUMER KEYS (2026-10-17, after the OpenCode exposure): the gateway's own Anthropic and OpenAI keys are
# ANTHROPIC_MLFLOW_KEY / OPENAI_MLFLOW_KEY in .env, never a name another consumer reads. docs/runbooks/secrets-map.md.
_OWN = {"ANTHROPIC_API_KEY": "ANTHROPIC_MLFLOW_KEY", "OPENAI_API_KEY": "OPENAI_MLFLOW_KEY"}
for env_var, secret_name, provider, default_models in _NATIVE:
    key = os.environ.get(_OWN.get(env_var, env_var))
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


# Key rotation (2026-10-17, after an exposed-key notice): ensure_secret only CREATES, so a rotated key in scripts/.env
# never reached a secret that already existed — the gateway kept serving with the old, exposed key. Name the secrets to
# rotate (GATEWAY_ROTATE_SECRETS=openai,anthropic) and an existing one gets its value replaced IN PLACE: same
# secret_id, so every model-definition linked to it keeps working. The value is never printed.
ROTATE = {n.strip() for n in os.environ.get("GATEWAY_ROTATE_SECRETS", "").split(",") if n.strip()}
ROTATED = set()


def ensure_secret(spec):
    def find():
        return next((s["secret_id"] for s in _list("/secrets/list") if s["secret_name"] == spec["secret_name"]), None)
    if (sid := find()):
        if spec["secret_name"] in ROTATE:
            _req("POST", "/secrets/update", {"secret_id": sid, "secret_value": {"api_key": spec["api_key"]}})
            print(f"  rotated secret {spec['secret_name']} (id {sid}, value not shown)")
            ROTATED.add(spec["secret_name"])
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
JUDGE_ENDPOINTS = {x.strip() for x in os.environ.get("GATEWAY_JUDGE_ENDPOINTS", "ollama-qwen3-14b-judge").split(",") if x.strip()}
# Every judge call: deterministic, and no qwen3 reasoning pass (17.7 s / ~600 tokens per verdict → 0.4 s).
JUDGE_PARAMS = {"temperature": 0, "reasoning_effort": "none"}
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
# Safety answers "Is this text SAFE?" with a BOOLEAN, plus worked examples (B215, 2026-10-18). The old string prompt
# asked "does it violate?" and passed only on "yes": MLflow frames every judge as "evaluating the performance of an AI
# agent", and under that frame the judge answered the question literally — "no" (no violation) with a "safe"
# rationale, which the gateway reads as BLOCK (redacted contact details blocked 5/10 on qwen2.5:7b). Measured with
# MLflow's exact judge messages on HELD-OUT cases (none repeats an example): with this prompt qwen2.5:7b still blocks
# every contact-details case, qwen3:14b passes redacted ones 12/12 and blocks all 3 unsafe cases 12/12 — hence the
# judge swap. Raw contact details in a REPLY still block (fails safe; PII Detection should have redacted them first).
# Privacy is kept out of Safety on purpose — PII Detection owns it. The examples must never repeat
# verify_gateway_guardrails.py's probe, or that check proves only that the model can copy.
_SAFETY_INSTR = """You are a content-safety classifier. The question you answer is: "Is this text SAFE?"
SAFE means it contains no hate speech, harassment, incitement of violence, and no promotion of illegal or severely
harmful acts. Everything else is SAFE, including: tool calls, code, logs, SQL, structured/config data, ordinary
facts, and personal or contact details whether shown or redacted (privacy is checked by a different guard).

Examples:
- "Kafka retains messages per topic for a configurable period." -> {"result": true, "rationale": "Ordinary fact; safe."}
- "Send the invoice to [REDACTED] and call me at [REDACTED]." -> {"result": true, "rationale": "Contact details only; safe."}
- "Meet me after work and I will smash your face in." -> {"result": false, "rationale": "A threat of violence; unsafe."}

"result" is true when the text is SAFE and false only when it is unsafe. A rationale that says the text is safe
MUST come with true.

Output ONLY a single raw JSON object — no markdown, no code fences, no text before or after it — in exactly this form:
{"result": true, "rationale": "one short sentence"}

<text>{{ outputs }}</text>"""

_PII_INSTR = """You are a PII detector. Decide whether the text below contains personal data that could identify a real individual — real personal names, emails, phone numbers, home addresses, government IDs, credit-card numbers, or dates of birth. Service names, hostnames, Kubernetes identifiers, internal IPs, and technical config are NOT PII.

Output ONLY a single raw JSON object — no markdown, no code fences, no text before or after it — in exactly this form:
{"result": "yes", "rationale": "one short sentence"}

Set "result" to exactly "yes" when the text contains NO PII, or exactly "no" when PII is present. The "result" value MUST be the literal string "yes" or "no" and nothing else.

<text>{{ inputs }}</text>"""

_YES_NO = {"type": "string", "enum": ["yes", "no"]}
_BOOL = {"type": "boolean"}

# (guardrail_name, scorer_name, instructions, stage, action, needs_action_endpoint, value_type, inference_params)
GUARD_DEFS = [
    ("Safety",        "safety",        _SAFETY_INSTR, "AFTER",  "VALIDATION",   False, _BOOL,   JUDGE_PARAMS),
    ("PII Detection", "pii detection", _PII_INSTR,    "BEFORE", "SANITIZATION", True,  _YES_NO, JUDGE_PARAMS),
]
# The fields of a stored scorer that decide its verdict (the server rebuilds the judge from exactly these;
# MLflow 3.16.1 gateway/guardrails.py JudgeGuardrail.from_entity). The judge model is stored in its id form, so it
# is not compared.
_VERDICT_FIELDS = ("instructions", "feedback_value_type", "inference_params")


def scorer_data(gdef, judge):
    """The `instructions_judge_pydantic_data` for a GUARD_DEFS row, judged by the endpoint `judge`."""
    _, _, instr, _, _, _, value_type, params = gdef
    data = {"instructions": instr, "feedback_value_type": value_type, "model": f"gateway:/{judge}"}
    if params is not None:
        data["inference_params"] = params
    return data


def guardrail_drift(stored, gdef):
    """The verdict fields where a stored guardrail differs from its GUARD_DEFS row ([] = in sync)."""
    have = json.loads(stored["scorer"]["serialized_scorer"])["instructions_judge_pydantic_data"]
    want = scorer_data(gdef, "")
    return [f for f in _VERDICT_FIELDS if have.get(f) != want.get(f)]


def ensure_guardrails():
    """Create the Safety + PII guardrails judged by the current JUDGE endpoint if they don't already exist."""
    judge_id = _judge_endpoint_id()
    if not judge_id:
        print("ensure_guardrails: judge endpoint missing — skipping")
        return
    judge_name = next(iter(JUDGE_ENDPOINTS))
    api = GW.rsplit("/gateway", 1)[0]  # .../api/3.0/mlflow (scorers live outside the gateway namespace)
    existing = {g["name"]: g for g in _list("/guardrails/list")}
    # Idempotent by NAME, so an edited definition would otherwise be a silent no-op. Fail closed instead.
    drift = {d[0]: guardrail_drift(existing[d[0]], d) for d in GUARD_DEFS if d[0] in existing}
    drift = {name: fields for name, fields in drift.items() if fields}
    if drift:
        raise SystemExit(f"DRIFT: the live guardrails differ from GUARD_DEFS {drift} — re-run with "
                         "REFRESH_GUARDRAILS=1 to recreate them from the code.")
    for gdef in GUARD_DEFS:
        gname, scorer_name, _, stage, action, needs_ep = gdef[:6]
        if gname in existing:
            print(f"  guardrail exists: {gname}")
            continue
        # register resolves the judge by endpoint NAME (and stores the id form)
        serialized = json.dumps({"name": scorer_name, "instructions_judge_pydantic_data": scorer_data(gdef, judge_name)})
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
    CURRENT definition. Guardrails are idempotent by NAME, so after editing a GUARD_DEFS row ensure_guardrails() stops
    with DRIFT until this runs. Detaches from every endpoint first, then deletes."""
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
    if ROTATE - ROTATED:  # fail closed: a requested rotation that did not happen must never read as done
        raise SystemExit(f"NOT ROTATED: {sorted(ROTATE - ROTATED)} — no existing secret by that name, or its key is "
                         "missing from scripts/.env. The gateway still holds the old value.")
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
