# weyland-tool-server — runbook

The lab's platform service boundary: RAG retrieval and answers (`/context/*`), per-backend health, the eval
triggers, Dagster launches, and the two MCP mounts agents use (`/mcp` to read, `/mcp-act` to act). Every agent action
in the lab goes through `/mcp-act` here. Routes and their contracts: [api.md § Tool server](../api.md). Written by
B239 (2026-11-08), which found no runbook for operating it.

## How it is built

- **Deployment** `weyland-tool-server` (ns `weyland`, 1 replica, Istio sidecar), manifest
  `k8s/weyland-tool-server.yaml`, code `services/weyland-tool-server/`. FastAPI on port 8080; NodePort **30080**
  (`http://192.168.1.243:30080`). There is no NetworkPolicy, so the read routes answer anywhere on the LAN. The act
  routes (`/mcp-act`, `/pipeline/trigger`, `/evals/run`, `/evals/score`) are denied to every caller except the MCP
  gateway's service account, by the Istio policy `toolserver-act-gateway-only` (`k8s/istio/authz-toolserver-act.yaml`).
  So an act from a laptop or the NodePort is refused before the guard is even asked.
- **Depends on:** core Postgres + pgvector, Qdrant, Weaviate, Neo4j (retrieval backends); Ollama on rogueone through
  its token-checked front door (`OLLAMA_API_KEY` from Secret `ollama-proxy-token`); `weyland-guard` for the
  input/output/act hooks ([guardrails.md](guardrails.md)); the Dagster webserver for `/pipeline/trigger`; MLflow for
  traces.
- **The act path fails closed:** `/pipeline/trigger`, `/evals/run` and `/evals/score` return **403** when the guard
  refuses or cannot be reached. The read path fails open: retrieval still answers if the guard is down, and the miss
  is counted.
- **Front doors for agents:** `https://mcp.weyland.lab` (Keycloak-authed, [mcp-gateway.md](mcp-gateway.md)) proxies
  `/mcp` and `/mcp-act`; Bifrost aggregates the read tools.
- **Image:** `registry.weyland.lab/weyland-tool-server:git-<sha>`, set by CI and shipped with
  `scripts/ship-images.sh` ([ship-images.md](ship-images.md)). Do not hand-edit the tag.

## Is it healthy?

```bash
kubectl -n weyland get deploy weyland-tool-server
```

One call reports the service, the query embedder, the LLM and every retrieval backend:

```bash
curl -s http://192.168.1.243:30080/status | python3 -c "import json,sys; d=json.load(sys.stdin); print('status', d['status'], '| llm', d['llm']['status'], '| embedder loaded', d['model']['loaded']); print({k: v.get('status') for k, v in d.get('backends', {}).items()})"
```

Expected (2026-11-08): `status ok | llm ok | embedder loaded True` and `{'pgvector': 'ok', 'qdrant': 'ok',
'weaviate': 'ok', 'neo4j': 'ok'}`. Per-backend detail: `/pgvector/health`, `/qdrant/health`, `/weaviate/health`,
`/neo4j/health`, `/ollama/health`. The pod's probes use `/health` (liveness) and `/ready` (readiness).

**Does retrieval actually work?** One read-only search (it changes nothing):

```bash
curl -s -X POST 'http://192.168.1.243:30080/context/search?backend=pgvector' -H 'Content-Type: application/json' -d '{"query":"woodpecker-cli pipeline create","limit":3}' | python3 -c "import json,sys; print([(r.get('source'), round(r.get('similarity',0),2)) for r in json.load(sys.stdin).get('results',[])])"
```

Expected: a non-empty list led by `woodpecker.md` / `weyland-image-ci.md` (similarity ~0.78).

**Are the guard hooks failing?**

```bash
curl -s http://192.168.1.243:30080/metrics | grep '^tool_server_guard_failures_total'
```

All zero is healthy. A rising `hook="act"` counter means agent actions are being refused (critical
`GuardCallsFailing`); `input`/`output` means retrieval runs unguarded (warning `GuardCallsFailing`).

## What broke? Symptom to cause

| Symptom | Likely cause | Check and fix |
|---|---|---|
| act tools / `/pipeline/trigger` return **403** | `weyland-guard` refused it (policy) or is down | the guard counter above; `kubectl -n weyland get deploy weyland-guard`; [guardrails.md](guardrails.md). A refusal by policy is correct behaviour |
| `/context/ask` errors or hangs, `llm` not ok in `/status` | Ollama on rogueone down, or the front-door token rejected | `/ollama/health`; [model-serving-ollama.md](model-serving-ollama.md) |
| one backend not `ok` in `/status` | that store is down or unreachable | the store's own runbook ([datasets-hydration.md](datasets-hydration.md), [service-mesh-istio.md](service-mesh-istio.md) for mTLS resets) |
| `400 encoded path separators are not accepted` | a path with `%2F` / `%5C` | by design (B207): Istio and uvicorn read such paths differently, so they are refused |
| pod restarting, `OOMKilled` | memory limit 3Gi | logs and `describe`, below |
| right documents exist but a natural-language question does not find them | retrieval precision, not a fault (B74) | search with the docs' own wording; for "how do I …" use `lab-ask` ([research-scratch-vault.md § Shortcuts](research-scratch-vault.md#shortcuts)) |

## Logs

```bash
kubectl -n weyland logs deploy/weyland-tool-server -c weyland-tool-server --tail=200
```

After a crash or restart (the reason, then the previous container's output):

```bash
kubectl -n weyland describe pod -l app=weyland-tool-server | grep -A3 -iE 'last state|reason'; kubectl -n weyland logs deploy/weyland-tool-server -c weyland-tool-server --previous --tail=200
```

Errors also reach GlitchTip (project via `SENTRY_DSN`, [glitchtip.md](glitchtip.md)); RAG calls leave MLflow traces
(experiment `tool-server-rag`).

## Restart

```bash
kubectl -n weyland rollout restart deploy/weyland-tool-server && kubectl -n weyland rollout status deploy/weyland-tool-server --timeout=180s
```

While it restarts, agents' MCP calls fail and act tools are unavailable. A restart does not pick up a new image:
that is `ship-images.sh`, and Argo reverts any hand edit (`selfHeal`).

## Monitoring

- Scraped by Prometheus (`up{job="weyland-tool-server"}`), with dashboard panels in the app-services dashboard.
- `GuardCallsFailing`: critical for the act hook, warning for input/output (`k8s/weyland-tool-server.yaml`).
- Down coverage is generic only (`TargetDown`, `KubePodNotReady`, both warning). There is no tool-server-specific
  critical alert although every agent act goes through it (B239 audit, finding 16).

## Related

- Routes: [api.md § Tool server](../api.md). Guard: [guardrails.md](guardrails.md). MCP front door:
  [mcp-gateway.md](mcp-gateway.md). Load baseline: [perf-baseline.md](perf-baseline.md).
- Restore: stateless; its data lives in the stores it reads (see `docs/dr.md`).
