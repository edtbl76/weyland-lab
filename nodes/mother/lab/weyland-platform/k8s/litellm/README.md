# LiteLLM — hosted-model gateway (Gemini + OpenRouter)

One OpenAI-compatible endpoint fronting **every** Gemini and OpenRouter model (wildcard routing), on the
LAN, for Hermes and any other consumer. Born from B26 (Claude brain — abandoned: subscription auth is a ToS
gray area, metered API declined). Reframed into the gateway that was always on the roadmap.

**Why this shape:** API keys (not subscription OAuth) → no ToS issue. Free tiers (Gemini AI Studio,
OpenRouter `:free`) → strong models at $0. Off-box valve + Prometheus metrics → governed egress.

## Keys (both free)
- Gemini: aistudio.google.com/apikey — free, no billing account.
- OpenRouter: openrouter.ai/keys — free account; `:free` models cost $0.

## Deploy (on mother)
Put a `/tmp/litellm.env` with three lines (`GEMINI_API_KEY=...`, `OPENROUTER_API_KEY=...`,
`LITELLM_MASTER_KEY=<random>`), then:
```
kubectl delete secret litellm-secrets -n weyland --ignore-not-found
```
```
kubectl create secret generic litellm-secrets -n weyland --from-env-file=/tmp/litellm.env
```
```
kubectl apply -f configmap.yaml -f deployment.yaml -f service.yaml -f servicemonitor.yaml -f ingress.yaml -f prometheusrule.yaml
```
```
shred -u /tmp/litellm.env
```
```
kubectl rollout restart deploy/litellm -n weyland
```

## Use it
From any LAN consumer at `http://192.168.1.243:30400/v1` (Bearer = `LITELLM_MASTER_KEY`). Request any model:
`gemini/gemini-2.5-pro`, `openrouter/deepseek/deepseek-r1:free`, `openrouter/meta-llama/llama-3.3-70b-instruct:free`,
or the aliases `gemini-flash` / `gemini-pro`. List what's live: `GET /v1/models`.

## Wire Hermes (CT 104)
Add a `custom` provider via `hermes model` (writes the correct schema; don't hand-edit). base_url
`http://192.168.1.243:30400/v1`, api_key = `LITELLM_MASTER_KEY`, model e.g. `gemini-flash`, api_mode
chat_completions. Default stays local (`qwen3-coder:30b`); escalate a turn with `/model <name> --provider <n>`.
Never add to `fallback_providers` or the auxiliary lanes (keeps background work local).

## Cut-off valve (./valve.sh — run on mother, agent can't reach it)
`./valve.sh close` stops all off-LAN model calls · `open` · `status`.

## Privacy note
Free tiers (Gemini free, OpenRouter free) may log/train on prompts. Fine for lab escalation; don't send
anything sensitive. Paid OpenRouter routes don't, but cost money — watch `LiteLLMSpendObserved`.

## Registries to update after deploy
`docs/hosts.md` (litellm.weyland.lab, NodePort 30400) · `docs/api.md` (/v1 endpoint) · `docs/arch.md` (egress edge).
