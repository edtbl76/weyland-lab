# Realm of Agents — runbook

24 corpus-backed agents in five realms, served by one pod as a conformant A2A server: a supervisor ("the Operator"
agent) discovers the others through their Agent Cards and delegates. UI: <https://realm.weyland.lab> (Keycloak
forward-auth). Design: `docs/design/a2a-agent-roster.md`; map: `docs/realm-of-agents-map.html`. Written by B239
(2026-11-08), which found no runbook for operating it.

## How it is built

- **Deployment** `realm-of-agents` (ns `weyland`, 1 replica), manifests `k8s/realm-of-agents/`, code
  `services/realm-of-agents/`. FastAPI on 8080 behind Service `realm-of-agents` and the ingress.
- **Who can reach it:** the NetworkPolicy `realm-of-agents-front-door-only` admits Traefik (people, through
  Keycloak), the operator, Dagster, the a2a-inspector, Bifrost's Agent Gateway and Prometheus; nothing else
  (the header of `k8s/realm-of-agents/netpol.yaml` lists why each one is there).
- **Model:** a paid turn goes to LiteLLM as `REALM_MODEL=wl-agentic` (Claude Haiku, routed through Bifrost); a
  free-only turn stays on the local models. **A2A calls are free-only unless they come through the Agent Gateway and
  ask for paid** (§ Through Bifrost's Agent Gateway). Tools come through Bifrost with the `agents-read` virtual key
  (`BIFROST_VK` from Secret `realm-of-agents-secret`, sealed). Runs are traced to Langfuse (sessions) and MLflow.
- **Surface:** `/` (UI), `/.well-known/agent-card.json` (the realm's card, 24 skills), `/agents` and
  `/agents/{key}/card` (per-agent cards), `/a2a` and `/a2a/{key}` (JSON-RPC: A2A v1 `SendMessage` and 0.3
  `message/send`; the cards advertise v1 in `supportedInterfaces`), `/route` and
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

## Through Bifrost's Agent Gateway (B249, 2026-11-19)

The operator calls the Realm through Bifrost's Agent Gateway (decision:
[ADR-0015](../adr/0015-adopt-bifrost-agent-gateway-for-the-realm.md)):

```
weyland-operator --SendMessage + x-bf-vk (realm-operator)--> Bifrost /agents/a2a/realm/json-rpc
Bifrost --SendMessage + X-Realm-Gateway-Token--> realm-of-agents /a2a
```

- **Grant:** the agent `realm` is granted to one virtual key, `realm-operator` (`allow_by_default` off). Bifrost
  refuses every other key. The caller's key is not forwarded; the Realm's agents use their own `agents-read` key for
  tools.
- **Paid lane:** a call runs paid only when it asks (`metadata.allow_paid: true`) AND carries
  `X-Realm-Gateway-Token` equal to the Realm's `REALM_GATEWAY_TOKEN`. Bifrost adds the header to every call it
  forwards (runtime auth `env.REALM_GATEWAY_TOKEN`), so **every key granted the Realm can spend**: granting another
  caller is a new decision. The 0.3 path and direct calls are free-only.
- **One id per conversation:** the A2A `contextId` is the Realm's dispatch session, and the Realm's MCP calls send it
  as `x-bf-session-id`. Bifrost's Agent Logs (UI Agents > Logs, `/api/agents/history`) show it next to the caller's
  key, and the MCP logs carry the same session id.
- **Where it lives:** the registration and the key are only in Bifrost's `config.db`;
  `scripts/register_bifrost_realm_agent.py` is their definition in git and rebuilds them. Secrets:
  `realm-gateway-token` (read by Bifrost and the Realm) and `weyland-operator-realm` (the operator's key), both sealed
  by `scripts/seal_realm_gateway.sh` from the gitignored `scripts/.env`.
- **When Bifrost is down,** delegation fails: the operator does not fall back to `/route` after a gateway error. It
  uses `/route` only when `REALM_GATEWAY_URL` or `REALM_GATEWAY_VK` is unset.

**Set it up or rebuild it**, in order:

1. The gateway settings (the private allowlist and the External Client URL; idempotent):

```bash
kubectl -n weyland exec -i deploy/weyland-guard -c weyland-guard -- env BIFROST_URL=http://bifrost.weyland.svc.cluster.local:8080 python - < /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/register_bifrost_client_config.py
```

2. The operator's key, appended to `scripts/.env`. It prints only `REALM_GATEWAY_VK=...`, so never run it without the
   redirect. `REALM_GATEWAY_TOKEN` must already be in the same file (any random value of 32 bytes or more):

```bash
kubectl -n weyland exec -i deploy/weyland-guard -c weyland-guard -- env BIFROST_URL=http://bifrost.weyland.svc.cluster.local:8080 python - ensure-vk < /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/register_bifrost_realm_agent.py >> /home/edwardmangini/IdeaProjects/weyland/scripts/.env
```

3. Seal both secrets (writes `k8s/sealed-secrets/sealed/weyland__realm-gateway-token.yaml` and
   `weyland__weyland-operator-realm.yaml`), then push them. Bifrost, the Realm and the operator read them on their
   next start:

```bash
bash /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/seal_realm_gateway.sh
```

4. Once the Realm serves the v1 card, register the agent:

```bash
kubectl -n weyland exec -i deploy/weyland-guard -c weyland-guard -- env BIFROST_URL=http://bifrost.weyland.svc.cluster.local:8080 python - register < /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/register_bifrost_realm_agent.py
```

5. Check it. Read-only; exit 1 names any drift, including a grant to any key other than `realm-operator`:

```bash
kubectl -n weyland exec -i deploy/weyland-guard -c weyland-guard -- env BIFROST_URL=http://bifrost.weyland.svc.cluster.local:8080 python - check < /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/register_bifrost_realm_agent.py
```

Expected: `OK: realm → http://realm-of-agents.weyland.svc.cluster.local:8080/.well-known/agent-card.json, granted to
realm-operator only, gateway token from env.REALM_GATEWAY_TOKEN`.

**Verify the path (free; no paid call):** one free-lane `SendMessage` from the operator's pod, with its own key:

```bash
kubectl -n weyland exec deploy/weyland-operator -c weyland-operator -- python -c 'import os,uuid,httpx; b={"jsonrpc":"2.0","id":"1","method":"SendMessage","params":{"message":{"messageId":uuid.uuid4().hex,"role":"ROLE_USER","parts":[{"text":"In one sentence, what is the Realm of Agents?"}],"metadata":{"allow_paid":False}}}}; r=httpx.post(os.environ["REALM_GATEWAY_URL"],json=b,headers={"x-bf-vk":os.environ["REALM_GATEWAY_VK"],"A2A-Version":"1.0"},timeout=240); j=r.json(); m=(j.get("result") or {}).get("message") or {}; print(r.status_code, j.get("error"), m.get("contextId"), m.get("metadata"), ((m.get("parts") or [{}])[0].get("text") or "")[:200])'
```

Expected: `200 None <contextId> {'routed_to': ..., 'realm': ...} <an answer>`. Bifrost UI > Agents > Logs then shows
the call under key `realm-operator` with the same context id. A JSON-RPC error naming the agent or the key means a
missing grant (run `check`); a 503 means the gateway settings are missing (step 1).

| Symptom | Likely cause | Check and fix |
|---|---|---|
| the operator's delegation fails with a gateway error | Bifrost down, or the agent not registered | Bifrost health ([mcp-gateway.md](mcp-gateway.md)); `check` above |
| the gateway answers 503 to every A2A call | `a2a_external_client_url` unset | step 1 |
| a task the operator sent as paid is answered by the free models | the token is missing on one side, or `runtime_auth` drifted | both pods have a non-empty `REALM_GATEWAY_TOKEN`; `check` |
| `check` says `DRIFT: granted to ...` | another key was granted in the UI | decide it; otherwise `register` puts the grant back to `realm-operator` only |

## Evaluation (B253, 2026-11-20)

Does the Realm's shape (Gná's routing, then a lead delegating to members) beat simpler shapes of itself on the same
free model? The deployed Realm runs three arms through `POST /eval/run {task, arm}`, always free-only (the local lane,
LiteLLM fallbacks off, and no paid tools: free-only also drops Perplexity, `fleet.PAID_TOOL_PREFIXES`):

| Arm | What runs |
|---|---|
| `realm` | Gná routes, and a lead delegates (the Realm as it is) |
| `routed` | Gná routes, and the chosen agent answers alone with its own tools (routing without delegation) |
| `single` | one agent holding every tool family the roster uses, no routing (the control) |

Each run returns the answer with its tokens, model calls, tool calls, delegations and seconds (a per-request callback
on the same hook as Langfuse). The 33 tasks, each with a rubric and the agents a correct router may pick, are in
`services/weyland-dagster/weyland_pipeline/eval_sets/realm.json`; CI fails if any task's text appears in the RAG corpus.
The judge is `wl-judge-oss` (gpt-oss:20b on rogueone, a different model from the one judged), blind to the arm, with
LiteLLM fallbacks off. Results: `eval/realm-b253/` (results.jsonl, scores.jsonl, report.md); write-up
`docs/concepts/realm-evaluation.md`.

Run it from rogueone (`kubectl` reaches the cluster from there); each mode resumes where it stopped, so rerun it after
any interruption. The full run (33 tasks x 3 arms x 3 reps) takes most of a night on rogueone's GPU:

```bash
bash /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/realm-eval.sh run
bash /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/realm-eval.sh judge
bash /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/realm-eval.sh report
```

`run` and `judge` exit 1 after two batches in a row make no progress (the Realm or the judge is down; the output says
which), and `report` refuses while a successful run is unjudged. A failed run is recorded and scores 0, never dropped.
Smaller runs: `REALM_EVAL_REPS=1`, or a different `REALM_EVAL_DIR`.

### Context-engineering trials (B255, 2026-11-21)

Two more arms test context engineering on the single agent (`context_trials.py`; verdicts in
[context-engineering.md § Trials](../concepts/context-engineering.md#trials)):

| Arm | What runs |
|---|---|
| `single-rt` | tool retrieval: only the 8 tools that best match the task (BM25 over each tool's name, the start of its description, and its family's roster text), instead of all 99 |
| `single-rs` | per-step retrieval (2026-11-22): the `single-rt` start, plus a `find_tools` tool; each call adds up to 5 matching tools, which the agent holds from its next step (langgraph-bigtool's pattern) |
| `single-ce` | context editing: past 4k tokens of messages, every tool result but the newest 2 is replaced with `[cleared]` in the model's view (LangChain's `ClearToolUsesEdit` semantics) |

Each `single-rt` and `single-rs` result lists its `retrieved` tools (and `single-rs` the tools it `found` mid-run); every result carries `cleared_tool_results`. Pick arms with
`REALM_EVAL_ARMS` (the default is B253's three), and keep a trial's results in their own directory:

```bash
REALM_EVAL_ARMS=single,single-rt,single-ce REALM_EVAL_DIR=/home/edwardmangini/IdeaProjects/weyland/eval/context-b255 bash /home/edwardmangini/IdeaProjects/weyland/nodes/mother/lab/weyland-platform/scripts/realm-eval.sh run
```

Then `judge` and `report` with the same `REALM_EVAL_DIR` (the arms matter only to `run`).

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
- Restore: stateless. The roster and prompts are in the image; its secrets are rebuildable, and its Bifrost registration is rebuilt by `register_bifrost_realm_agent.py` (`docs/dr.md`).
