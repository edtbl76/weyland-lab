# Secrets map — which system uses which provider key

Every model-provider key the lab holds, by its variable name in the gitignored `scripts/.env` on rogueone, the system
that uses it, how it gets there, and how to rotate it. **Names only — never a value.** The mechanics of sealing and
restoring live in [secrets.md](secrets.md); this page is the *who uses what*.

Created 2026-10-17 after the lab's Google, Anthropic and OpenAI keys were exposed through OpenCode's old web console
and the shared Anthropic key was used by someone else (~$60 in one day; the lab's own Anthropic spend over the prior
30 days was $0.0013). All three were rotated; the Google (Gemini) key's rotation was confirmed by the owner on 2026-10-19. The rule since: **one key
per consumer**, so a leak means revoking one key and touching one system.

## Model-provider keys

| Variable (`scripts/.env`) | Provider · owner type | Used by | How it gets there | Rotate |
|---|---|---|---|---|
| `ANTHROPIC_BIFROST_KEY` | Anthropic · user-bound | **Bifrost** | `seal_bifrost_keys.sh` seals it into SealedSecret `weyland/bifrost-provider-keys` as `ANTHROPIC_API_KEY`; Bifrost loads that secret as env (`envFrom`) and its provider refers to `env.ANTHROPIC_API_KEY` | § Bifrost |
| `OPENAI_BIFROST_KEY` | OpenAI · service account `weyland-bifrost` (project `weyland`, Restricted: List models read, Chat completions + Responses write) | **Bifrost** | same, sealed as `OPENAI_API_KEY` | § Bifrost |
| `ANTHROPIC_LITELLM_KEY` | Anthropic · user-bound | **LiteLLM** | patched into SealedSecret `weyland/litellm-secrets` key `ANTHROPIC_API_KEY`; LiteLLM reads it as `LITELLM_ANTHROPIC_API_KEY` (`k8s/litellm/deployment.yaml`, used by `configmap.yaml`) | § LiteLLM |
| `ANTHROPIC_MLFLOW_KEY` | Anthropic · user-bound | **MLflow AI Gateway** | `register_gateway_endpoints.py` stores it in the MLflow database as gateway secret `anthropic` | § MLflow gateway |
| `OPENAI_MLFLOW_KEY` | OpenAI · service account (project `weyland`, Restricted: Chat completions + Responses write) | **MLflow AI Gateway** | same, gateway secret `openai` | § MLflow gateway |
| `ANTHROPIC_OPENCODE_WORKSPACE_KEY` | Anthropic · user-bound, its **own workspace** with a lower spend limit | **OpenCode only** (rogueone, interactive) | passed at launch as `ANTHROPIC_API_KEY` in an otherwise empty environment ([coding-agents.md](coding-agents.md) § Launch) — never sealed, never in a cluster | revoke + recreate in the Console, nothing else to update |
| `OPENCODE_ZEN_API_KEY` | OpenCode Zen | **Bifrost** (`opencode-zen` provider) and **LiteLLM** (via Bifrost's secret) | sealed into `weyland/bifrost-provider-keys` by `seal_bifrost_keys.sh` | § Bifrost — *issued by OpenCode; NOT part of the 2026-10-17 exposure (owner: only the Google, Anthropic and OpenAI keys were exposed from the web console), so not rotated* |

Not provider keys, listed so nobody hunts for them: Open WebUI's `OPENAI_API_KEY` is the dummy `nemo-guardrails`
(it talks to the guardrails service); the eval scripts set `OPENAI_API_KEY` to `gateway`/`ollama`; Codex uses a ChatGPT
sign-in, not an API key. Other providers' keys (Gemini, Groq, Mistral, …) are still shared names in `.env`, sealed into
`bifrost-provider-keys` for Bifrost and LiteLLM.

Spend caps: Anthropic — the lab workspace $200/month; OpenCode's workspace lower. OpenAI — project `weyland`'s budget.
Keys do not expire (reminders do not get acted on here); the caps bound a leak instead. Short-lived credentials: B217.

## Rotate

Edit the new value into `scripts/.env` yourself — never paste a key into chat. Then, per consumer (all on rogueone):

### Bifrost (and OpenCode Zen)
```
bash /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/seal_bifrost_keys.sh
```
It stops (exit 1) if `ANTHROPIC_BIFROST_KEY` or `OPENAI_BIFROST_KEY` is missing rather than sealing a secret without
it. Commit + push the changed `k8s/sealed-secrets/sealed/weyland__bifrost-provider-keys.yaml`, wait for Argo to show
`sealed-secrets-manifests` Synced on that commit, then restart (env is read at start):
```
kubectl -n weyland rollout restart deploy/bifrost deploy/litellm
```
(LiteLLM reads Bifrost's secret for OpenCode Zen and the other shared providers, so it restarts too.)

### LiteLLM (its Anthropic key)
```
set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a && printf '{"data":{"ANTHROPIC_API_KEY":"%s"}}' "$(printf %s "$ANTHROPIC_LITELLM_KEY" | base64 -w0)" | kubectl -n weyland patch secret litellm-secrets --patch-file=/dev/stdin && kubectl -n weyland get secret litellm-secrets -o yaml | kubeseal --format yaml > /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/k8s/sealed-secrets/sealed/weyland__litellm-secrets.yaml
```
It patches ONLY that key — `litellm-secrets` holds others (master key, Langfuse) that a `create secret` would drop.
Commit + push the sealed file, wait for Synced, then `kubectl -n weyland rollout restart deploy/litellm`.

### MLflow gateway
```
GATEWAY_ROTATE_SECRETS=openai,anthropic python3 /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/register_gateway_endpoints.py
```
Replaces the stored value IN PLACE (same secret id, so every model definition stays linked) and must print
`rotated secret openai` and `rotated secret anthropic`; a name it could not rotate exits 1 `NOT ROTATED`. No restart.

## Verify after a rotation
Never trust "it applied": check each system authenticates with the new key (a model-list call through Bifrost, a call
through LiteLLM, the gateway's masked value changed in `/api/3.0/mlflow/gateway/secrets/list`), and that the old key
is revoked in the provider console.
