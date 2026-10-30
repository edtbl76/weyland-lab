# Demo — Model Gateway (LiteLLM) + Backend Dispatch

Two related routing surfaces in one demo:

1. **LiteLLM model gateway** — a single OpenAI-compatible endpoint on mother that fronts every
   Gemini + OpenRouter model (wildcard routing), with a human-only egress valve and spend alerts.
2. **Backend dispatch** — how the tool-server's `/context/*` picks one of the 4 vector backends
   (single-dispatch per request; `backend=all` is rejected).

Grounded in [runbooks/model-gateway.md](../runbooks/model-gateway.md),
[diagrams/flow-model-gateway.md](../diagrams/flow-model-gateway.md), and
[diagrams/flow-backend-dispatch.md](../diagrams/flow-backend-dispatch.md).

## Sequence diagram

Gateway routing — reused from [diagrams/flow-model-gateway.md](../diagrams/flow-model-gateway.md):

```mermaid
sequenceDiagram
    participant Cl as Client (Hermes planning / Open WebUI / curl)
    participant LL as LiteLLM /v1 (mother:30400, litellm.weyland.lab)
    participant GM as Gemini (free tier)
    participant OR as OpenRouter (free models)
    participant PM as Prometheus (request + spend)
    participant Tg as Telegram (alerts)
    Cl->>LL: POST /v1/chat/completions {model}
    LL->>LL: resolve model -> provider route
    alt Gemini-mapped
        LL->>GM: egress (off-box)
        GM-->>LL: completion
    else OpenRouter-mapped
        LL->>OR: egress (off-box)
        OR-->>LL: completion
    end
    LL->>PM: emit request + spend metrics
    LL-->>Cl: completion
    Note over PM,Tg: spend / off-box-egress alert -> Alertmanager -> Telegram
```

Backend dispatch — reused from [diagrams/flow-backend-dispatch.md](../diagrams/flow-backend-dispatch.md):

```mermaid
sequenceDiagram
    participant Cl as Client
    participant TS as tool-server /context/search
    participant Fn as Selected backend fn (SEARCH_FNS[backend])
    participant Emb as bge embedding
    participant Back as pgvector | qdrant | weaviate | neo4j
    Cl->>TS: GET /context/search {query, backend=pgvector (default)}
    alt backend not in {pgvector,qdrant,weaviate,neo4j}
        TS-->>Cl: 400 (e.g. backend=all rejected)
    else valid backend
        TS->>Fn: dispatch SEARCH_FNS[backend]
        Fn->>Emb: embed(query)
        Fn->>Back: vector search top-k
        Back-->>Fn: chunks
        Fn-->>TS: ranked chunks
        TS-->>Cl: results
    end
```

## Prerequisites

- **mother** (`192.168.1.243`) — LiteLLM at NodePort `30400` (`http://mother:30400/v1`, UI
  `litellm.weyland.lab`), tool-server at `30080`, and the 4 vector backends (pgvector/qdrant/
  weaviate/neo4j).
- LiteLLM secret `litellm-secrets` in ns `weyland` holds `LITELLM_MASTER_KEY` (+ `GEMINI_API_KEY` /
  `OPENROUTER_API_KEY`). Egress **valve** must be open (replicas=1) for hosted-model calls.
- Free API keys already configured (Gemini free tier + OpenRouter free models).

## UI walkthrough

- **LiteLLM admin UI** — `https://litellm.weyland.lab` (`/ui`) — model list, keys, spend.
- **Grafana** — `https://grafana.weyland.lab` — LiteLLM request/spend metrics (job `litellm`).
- **Tool-server API docs** — `http://mother:30080/docs` — `/context/search` and `/context/ask`
  (the `backend` param).

## CLI walkthrough

**Gateway** — pull the master key from the secret (no placeholder), list served models, run a real
Gemini completion:

```
[mother] MK=$(kubectl get secret litellm-secrets -n weyland -o jsonpath='{.data.LITELLM_MASTER_KEY}' | base64 -d)
```

```
[mother] curl -s http://192.168.1.243:30400/v1/models -H "Authorization: Bearer $MK" | head -c 400; echo
```

```
[mother] curl -s http://192.168.1.243:30400/v1/chat/completions -H "Authorization: Bearer $MK" -H "Content-Type: application/json" -d '{"model":"gemini-flash","messages":[{"role":"user","content":"say hi in 3 words"}]}' | head -c 500; echo
```

Confirm the metrics target is up:

```
[mother] kubectl exec -n monitoring "$(kubectl get pod -n monitoring -l app.kubernetes.io/name=prometheus -o name | head -1)" -c prometheus -- promtool query instant http://localhost:9090 'up{job="litellm"}'
```

Query the model catalog (which hosted models are reachable + free) — populated by the Dagster
`model_catalog` asset:

```
[mother] kubectl exec -i -n weyland deploy/weyland-postgres -- psql -U weyland -d weyland -c "SELECT source, count(*), count(*) FILTER (WHERE free) AS free FROM model_catalog GROUP BY source;"
```

**Backend dispatch** — valid backend (default is `pgvector`); then show that `backend=all` is
rejected with a 400:

```
[mother] curl -s -X POST "http://mother:30080/context/search?backend=pgvector" -H "Content-Type: application/json" -d '{"query":"how is the eval leaderboard computed?"}'
```

```
[mother] curl -s -o /dev/null -w '%{http_code}\n' -X POST "http://mother:30080/context/search?backend=all" -H "Content-Type: application/json" -d '{"query":"anything"}'
```

Same single-dispatch on `/context/ask` (backend is a **body** field there, not a query param):

```
[mother] curl -s -X POST http://mother:30080/context/ask -H "Content-Type: application/json" -d '{"query":"how is the eval leaderboard computed?","backend":"qdrant"}'
```

### Private lane fails closed (B234)

The guarantee of a `wl-private-*` alias, shown end to end with OJay Floyd's own key (from `scripts/.env`, never printed).
The keyed calls (steps 1, 2 and 4) are this one command; step 3 is in the runbook:

[rogueone]
```
set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a && for m in wl-private-rag wl-default; do curl -s -o /dev/null -w "$m %{http_code}\n" -m 240 -H "Authorization: Bearer $OJAY_FLOYD_LITELLM_KEY" -H 'Content-Type: application/json' -d "{\"model\":\"$m\",\"max_tokens\":200,\"messages\":[{\"role\":\"user\",\"content\":\"Reply with: ok\"}]}" http://192.168.1.243:30400/v1/chat/completions; done
```

1. **Ollama up:** `wl-private-rag 200` (header `x-litellm-model-api-base: http://192.168.1.230:11434`, rogueone).
2. **Out of scope:** `wl-default 403` — the key can only reach the private lanes, so even a hosted alias named in the
   request (or a request-body `fallbacks`) is refused.
3. **Valve off:** `sudo systemctl stop ollama.service` on rogueone, re-run → `wl-private-rag 500` (front door `502`),
   then `sudo systemctl start ollama.service`. LiteLLM's log says `No fallback model group found for original
   model_group=wl-private-rag … Available Model Group Fallbacks=None`.
4. **Nothing left the LAN:** Bifrost's upstream counter does not move over the window
   (`sum(increase(bifrost_upstream_requests_total[3m]))` = 0), and LiteLLM's spend log holds one `failure` row per call
   with no provider.

Recorded run, 2026-10-30 13:58 UTC: 1 `200` / 2 `403` / 3 `500` + `500` (`wl-private-reason` too) / 4 Bifrost upstream
increase **0**, spend-log rows `eaa9f1f5…` and `3c66182c…` both `failure`. While Ollama is stopped the operator falls back
to Haiku (paid), so keep the window to a minute.

## Expected result

- `/v1/models` lists the wildcard-routed Gemini + OpenRouter catalog; the `gemini-flash` completion
  returns a short off-box answer through the valve.
- `up{job="litellm"}` returns `1`.
- `model_catalog` counts resemble the first populated run: openrouter ~336 (26 free), gemini ~37,
  ollama 6.
- Backend dispatch: `backend=pgvector`/`qdrant` returns ranked chunks; **`backend=all` returns
  `400`** (no fan-out/compare-all mode exists).

## Cleanup / teardown

Mostly **read-only** — these calls create no lab data beyond LiteLLM's per-request spend-log rows (since B234 LiteLLM
keeps virtual keys + spend logs in its `litellm` database; the demo mints no key); `/context/*`
reads the vector stores; `model_catalog` is refreshed by its own 6h asset, replace-by-source). The
one stateful lever is the **egress valve** — if you opened it only for the demo, close it so no
off-LAN calls stay possible (`./valve.sh status` shows whether it is open; the spend alerts guard cost — `BifrostSpendObserved` for routes via Bifrost, `LiteLLMSpendObserved` for the direct routes that bypass it, $1/24h each, see [runbooks/model-gateway.md](../runbooks/model-gateway.md) §3):

```
[mother] ./valve.sh close
```

```
[mother] ./valve.sh status
```

> `valve.sh` is the human-only cut-off from the runbook (lives on mother; agents cannot reach it).
> TODO: verify its path on mother if not on `$PATH`.
