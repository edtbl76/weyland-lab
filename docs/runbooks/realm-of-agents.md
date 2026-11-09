# Realm of Agents — runbook

24 corpus-backed agents in five realms, served by one pod as a conformant A2A server: a supervisor ("the Operator"
agent) discovers the others through their Agent Cards and delegates. UI: <https://realm.weyland.lab> (Keycloak
forward-auth). Design: `docs/design/a2a-agent-roster.md`; map: `docs/realm-of-agents-map.html`. Written by B239
(2026-11-08), which found no runbook for operating it.

## How it is built

- **Deployment** `realm-of-agents` (ns `weyland`, 1 replica), manifests `k8s/realm-of-agents/`, code
  `services/realm-of-agents/`. FastAPI on 8080 behind Service `realm-of-agents` and the ingress.
- **Reachable only through Traefik** (and Prometheus for metrics): the NetworkPolicy
  `realm-of-agents-front-door-only` admits nothing else, so in-cluster callers use the ingress too.
- **Model:** every agent turn goes to LiteLLM as `REALM_MODEL=wl-agentic` (Claude Haiku, routed through Bifrost).
  **Each dispatch is a paid call.** Tools come through Bifrost with the `agents-read` virtual key
  (`BIFROST_VK` from Secret `realm-of-agents-secret`, sealed). Runs are traced to Langfuse (sessions) and MLflow.
- **Surface:** `/` (UI), `/.well-known/agent-card.json` (the realm's card, 24 skills), `/agents` and
  `/agents/{key}/card` (per-agent cards), `/a2a` and `/a2a/{key}` (JSON-RPC `message/send`), `/route` and
  `/route/stream` (dispatch through the supervisor), `/health`, `/ready`, `/metrics`.
- **Image:** `registry.weyland.lab/realm-of-agents:git-<sha>`, set by CI and shipped with `scripts/ship-images.sh`.

## Is it healthy?

```bash
kubectl -n weyland get deploy realm-of-agents
```

From inside the pod (the NetworkPolicy keeps everything else out):

```bash
kubectl exec -n weyland deploy/realm-of-agents -c realm-of-agents -- python3 -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=10).read().decode()); print(urllib.request.urlopen('http://127.0.0.1:8080/ready', timeout=10).read().decode())"
```

Expected (2026-11-08): `{"status":"ok","service":"realm-of-agents","version":"0.3.5","agents":24}` and
`{"status":"ready"}`. `/ready` returns 503 `loading` while the roster loads at start-up.

The Agent Cards load without calling a model, so they are a free check that the roster is intact:

```bash
kubectl exec -n weyland deploy/realm-of-agents -c realm-of-agents -- python3 -c "import json,urllib.request; c=json.load(urllib.request.urlopen('http://127.0.0.1:8080/.well-known/agent-card.json', timeout=10)); print(c['name'], len(c.get('skills', [])), 'skills')"
```

Expected: `Realm of Agents 24 skills`.

**A real dispatch** (`/route`, or a message in the UI) is the only end-to-end test, and it costs a Haiku call per
agent turn. Use the UI for one message when you need it; the A2A Inspector (`inspector.weyland.lab`) validates the
A2A surface without dispatching.

## What broke? Symptom to cause

| Symptom | Likely cause | Check and fix |
|---|---|---|
| `/route` returns **502** "Dispatch failed" | LiteLLM or the `wl-agentic` route failed: provider error, budget, or Bifrost | LiteLLM's health and spend ([model-gateway.md](model-gateway.md)); Bifrost ([mcp-gateway.md](mcp-gateway.md)) |
| agents answer but cannot use tools | the Bifrost `agents-read` virtual key is missing, wrong or revoked | the Secret is sealed; re-create the VK and re-seal per [secrets.md](secrets.md) (credential steps are the owner's) |
| `/ready` stays 503 `loading` | the roster or its prompts failed to load at start-up | the logs, below |
| runs missing from Langfuse | Langfuse down; dispatch still works | [langfuse.md](langfuse.md) |
| the UI shows a Keycloak login loop | forward-auth, not the Realm | [keycloak.md](keycloak.md) |

## Logs

```bash
kubectl -n weyland logs deploy/realm-of-agents -c realm-of-agents --tail=200
```

## Restart

```bash
kubectl -n weyland rollout restart deploy/realm-of-agents && kubectl -n weyland rollout status deploy/realm-of-agents --timeout=180s
```

A dispatch in flight is lost. Argo reverts hand edits to the Deployment (`selfHeal`); a new image is a ship.

## Monitoring

Prometheus scrapes `/metrics` (ServiceMonitor `realm-of-agents`): `realm_requests_total` and
`realm_request_seconds`. No alert targets the Realm specifically; the generic `TargetDown` and `KubePodNotReady`
(warning) cover it going down. Model spend shows in LiteLLM's spend alerts.

## Related

- Who calls it: the B66 operator over A2A ([operator.md](operator.md)). Model routing: [model-gateway.md](model-gateway.md).
- Restore: stateless. The roster and prompts are in the image; its one secret is rebuildable (`docs/dr.md`).
