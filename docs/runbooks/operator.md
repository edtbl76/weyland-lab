# Operator agent — the `weyland-operator` service (B66)

Text the lab from anywhere → it acts. A LangGraph ReAct agent — **local `qwen2.5:7b` primary, Haiku failover** — over
the tool-server's read + act tools plus the MCP fleet, fronted by **Telegram long-poll**, with **per-chat Postgres
session memory** and an **app-level confirm-step** on every state-changing action. It also runs the **B45 incident
sweep** (below). This is the operator lane **Hermes vacated** (CT-104 destroyed 2026-07-23) — a k8s pod
on mother, not an LXC. `weyland-operator.weyland.svc:8080` (ClusterIP, no ingress — long-poll is outbound).

## The three parts (as built)
1. **Agent core** — `create_react_agent(llm, tools)`; read tools (`status`, `context_search`, `context_ask`)
   called freely; native tool-calling. `POST /operator/ask {message}` is the stateless test/probe surface.
2. **Ingress + memory** — a Telegram `getUpdates` long-poll task; per allowlisted message: guard-in → load session →
   agent → guard-out → reply → persist. History is the last 10 turns in Postgres (`operator_sessions`, per `chat_id`).
3. **Act + confirm-step** — the agent can only `propose_act`; the **app** fires (via `act.py`) only on an explicit
   user "yes". Four rails stack (below).

## The confirm-step (the safety rail)
```
propose (LLM) → store pending_action → "⚠️ Confirm …? yes/no" → user "yes" → app fires (act.py → tool-server)
```
- The act endpoints are **never bound to the LLM** — only `propose_act` is (it just records intent). `agent.run`
  returns `(reply, proposal)`; the proposal is read off the **tool-call trace**, not the model's prose.
- **Five independent rails:** (1) Telegram **allowlist** (`TELEGRAM_ALLOWED_USERS`) · (2) **confirm-step**
  (app-fires-on-yes) · (3) `act.py` **fail-closed** `JOB_ALLOWLIST` (unknown tool/job refused before any HTTP) ·
  (4) the tool-server's own **`Hook.ACT`** guard on the launch · (5) the **MCP gateway** injects a Keycloak-verified
  actor + the guard's enforcing **`policy.gate`** (identity-required allowlist + per-actor rate-cap). Any one holding
  is enough.
- Acts are **Telegram-only** (the confirm needs a session). `/operator/ask` surfaces a proposal but never fires.
- The 3 acts → the tool-server's `/mcp-act` jobs: `pipeline_trigger` (`job_name` ∈ `weyland_ingestion_job` /
  `weyland_eval_job` / `weyland_eval_score_job`), `evals_run`, `evals_score`.
- **Actor (B17+B19):** acts route through the **MCP gateway** (`mcp.weyland.lab`) with a Keycloak `client_credentials`
  token — the gateway validates it and injects the **verified** actor `weyland-operator` (the client_id), which is what
  the enforcing `policy.gate` allowlists. With no client secret wired (`OPERATOR_CLIENT_SECRET` unset), `act.py` falls
  back to the legacy direct path, self-setting `operator:telegram:<chat_id>`. See
  [runbooks/mcp-gateway.md](mcp-gateway.md) / [[b17-b19-mcp-gateway]].

## Architecture decisions (see the B66 design doc)
- **Brain = local `qwen2.5:7b` primary, Haiku failover** (B45 follow-up, 2026-08-04) — the local model is **$0**,
  non-thinking, and tool-calls cleanly on a **curated FLAT toolset** (`READ_TOOLS` + ~14 ops tools via `LOCAL_FLEET_ALLOW`).
  The full ~91-tool fleet *and* the two-stage **routers** (the old `FLEET_ROUTING`, now retired) both broke small-model
  tool selection — the routers made it emit *malformed* tool-calls; a handful of real flat tools tool-calls perfectly
  (proven: one tool → a clean structured `tool_call` in ~2.7s). **Haiku** (via **LiteLLM** — a *transparent* passthrough
  proxy so tool schemas survive; **NOT** the MLflow AI Gateway, whose normalization shreds them) is a **health failover
  only**: `agent.run` picks local unless a fast `/api/tags` pre-check (cached 30s) misses OR a call errors/stalls past
  `OPERATOR_LOCAL_TIMEOUT=60s`, then it re-runs on Haiku (which gets the full flat 91). Steady-state Haiku spend ≈ **$0**;
  watch `operator_brain_selected_total{brain,reason}` — Haiku selections are the failover signal. Env: `OLLAMA_MODEL=qwen2.5:7b`,
  `OLLAMA_FALLBACK_MODEL=claude-haiku`, `OPERATOR_LLM_FALLBACK=1`, `OLLAMA_HEALTH_URL`. See
  [flow-operator-brain.md](../diagrams/flow-operator-brain.md), [[operator-local-brain-qwen25-flat]].
- **Fleet tools (B17+B19 Phase 3)** — loads the composed fleet's ~90 read tools from the gateway `/mcp-fleet`
  (grafana/trino/k8s/postgres/neo4j/datahub) via `langchain-mcp-adapters` + a per-request token-refreshing `httpx.Auth`;
  MCP schemas sanitized; the **local brain gets a curated FLAT subset** (`LOCAL_FLEET_ALLOW`, ~14 tools), the **Haiku
  failover gets all ~91 flat** (routers retired). Guardrails stay at the EDGE (weyland-guard in/out + confirm-step),
  never inline in the LLM path. Demo/list: [demos/mcp-fleet.md](../demos/mcp-fleet.md).
- **Fresh LangGraph shell, not Hermes/OpenClaw** — the brain (their weakness) is fixed; we own the confirm-step rail.
- **Raw httpx for Telegram**, not python-telegram-bot — the loop is just `getUpdates` + `sendMessage`; fewer deps.
- **`asyncio.to_thread`** wraps the blocking agent + psycopg2 calls so the single event loop stays free for `/health`
  and the long-poll.
- **Per-op Postgres connections** (not a pool) — sidesteps the Envoy long-connection stall (the Neo4j-Bolt lesson);
  a chat bot's volume makes it free. STRICT-mTLS → the pod is **meshed**.
- **Guards** via the shared **weyland-guard** (INPUT on the message, OUTPUT on the reply/proposal), **fail-open**.

## MLflow tracing
`mlflow.langchain.autolog()` → one Trace per handled message, experiment **`operator`** at `mlflow.weyland.lab`.
⚠️ Same gotcha as weyland-agent: autolog needs the full **`langchain`** package in the image (langchain-openai/langgraph
only pull langchain-core), else it silently no-ops.

## Build & deploy (registry flow)
- Build + push (**rogueone**): `docker build -t registry.weyland.lab/weyland-operator:vN <services/weyland-operator> && docker push registry.weyland.lab/weyland-operator:vN`
- **Registry manifest defect (B101 — fixed):** the manifest PUT intermittently doesn't finalize on the first push
  (tag absent → `ImagePullBackOff: not found`). Push via **`scripts/push-image.sh registry.weyland.lab/weyland-operator:vN`**
  — it pushes, verifies the tag landed in `/v2/.../tags/list`, and auto-re-pushes if not (a re-push re-sends the small
  manifest, which lands). Deploy in one command instead of a manual round-trip.
- Manifests: `k8s/weyland-operator/{deployment,service,servicemonitor}.yaml`; Argo app in `subdir-apps.yaml`. **Meshed**;
  memory request kept low (256Mi, no torch — the operator calls the tool-server for retrieval).
- **Secret** `weyland-operator-secret` (`TELEGRAM_BOT_TOKEN` + `TELEGRAM_ALLOWED_USERS`) — SealedSecret (GitOps) or a
  manual create. Refs are `optional: true` → the pod starts HTTP-only without it (graceful `telegram.configured()`).

## Gotchas
- **Strip the `bot` prefix** from the token: `/bot<TOKEN>/` — the `bot` is the URL path, the stored value is the bare
  `<id>:<hash>`. Store it with `bot` → every call 404s.
- **getUpdates ownership** — once the pod runs with the token, it owns the long-poll; a manual `curl …/getUpdates`
  from elsewhere competes. Get your `chat_id` (message the bot, then `curl …/getUpdates`) **before** the pod is live.
- **Bot mint** — the old Hermes bot token died with `~/.hermes/.env` on CT-104; the operator uses a **fresh** @BotFather
  bot. Separate bot from the Kuma/Alertmanager paging.

## Verify (on mother)
```
kubectl -n weyland logs deploy/weyland-operator | grep -i telegram
```
→ `long-poll ingress started`. Then DM the bot:
- "is the lab healthy?" → grounded reply (calls `status`).
- "which of those is the graph store?" → "neo4j" (session memory carried the prior turn).
- "run the ingestion pipeline" → **⚠️ Confirm** prompt, nothing fired; "no" → cancelled; "yes" → `✅ Launched weyland_ingestion_job — run …`.

**Verified actor through the gateway (B17+B19):** after a confirmed act, the guard's `policy.gate` records the injected actor —
```
kubectl -n weyland logs deploy/weyland-guard --tail=40 | grep -i "policy.gate\|actor"
```
→ `actor=weyland-operator` (the gateway-injected client_id). A `<NULL>` or `operator:telegram:<chat_id>` actor here means the act bypassed the gateway (no `OPERATOR_CLIENT_SECRET`) — it must read `weyland-operator` before `policy.gate` is flipped from SHADOW to `block`.

## Incident sweep (B45) — enrich-only, off the critical path
A background loop (`incidents.py`, `INCIDENT_SWEEP_INTERVAL=180s`) reads `ALERTS{alertstate="firing"}` from Prometheus
(`PROMETHEUS_URL` = `prometheus-operated.monitoring.svc:9090` — one query unifies every firing rule incl. the blackbox
synthetic downs), dedups against Postgres (`operator_incidents`, one notify per firing episode), and for each **new**
incident runs the agent to **enrich** it (correlate recent logs + pod status via the fleet) → posts a proactive Telegram
digest. **Enrich-only** — any act the agent proposes is dropped. **Hard rule:** it never sits in the paging path — direct
Kuma/Alertmanager→Telegram stays the pager, so if this loop dies paging is unaffected. Noise filter: skips
`severity=none` + `INCIDENT_SKIP_ALERTS` (Watchdog, InfoInhibitor, LiteLLMEgressEnabled). Gated on
`INCIDENT_SWEEP_ENABLED=true` + Telegram configured + a target chat. Metrics `operator_incident_sweeps_total{outcome}` /
`operator_incidents_notified_total`; alerts `WeylandOperatorDown` + `WeylandOperatorSweepErrors`
(`k8s/weyland-operator/prometheusrule.yaml`). See [flow-incident-sweep.md](../diagrams/flow-incident-sweep.md).

## Diagnosing a slow / stalled local brain
The local brain shares rogueone's **16 GB GPU** (RAG embedder + on-demand llama-guard-8b + the display). If the operator
hangs or every request fails over to Haiku, **prove which layer before swapping models** — isolate with bounded direct
calls from the pod:
```
# reachable + what's loaded + is the model FULLY on GPU (offload = slow):
kubectl -n weyland exec deploy/weyland-operator -- python -c "import httpx; ps=httpx.get('http://192.168.1.230:11434/api/ps',timeout=5).json().get('models',[]); print([(m['name'], str(round(100*m['size_vram']/m['size']))+'%GPU') for m in ps])"
# one trivial call — fast? does the tool-call PARSE (structured vs leaked into content)?
kubectl -n weyland exec deploy/weyland-operator -- python -c "import httpx,time; t=time.time(); r=httpx.post('http://192.168.1.230:11434/v1/chat/completions', json={'model':'qwen2.5:7b','messages':[{'role':'user','content':'reply with the single word ok'}]}, timeout=60); print(round(time.time()-t,1),'s', r.json()['choices'][0]['message'])"
# which brain actually served — local vs haiku failover:
kubectl -n weyland exec deploy/weyland-operator -- python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8080/metrics').read().decode())" | grep 'operator_brain_selected_total{'
```
- **`<100% on GPU`** → CPU offload (VRAM contended). Free it: `./scripts/llama-guard-8b.sh stop` on rogueone (llama-guard-8b holds ~6 GB; it's on-demand). The 14.4 GB gpt-oss:20b never fits the shared card — that's why the brain is a 7B.
- **tool-call leaked into `content`** (a `</tool_call>` blob, no `tool_calls`) → too many / router-wrapped tools; the local brain needs the **curated FLAT set**, not routers or the full 91.
- **Ollama `/v1` won't disable qwen3 thinking** — `think:false`, `/no_think`, and `chat_template_kwargs.enable_thinking:false` are ALL no-ops on this build (the reasoning field stays populated); use a **non-thinking** model (qwen2.5:7b), don't fight it. See [[operator-local-brain-qwen25-flat]].

## Reliability check (periodic — run ~1 day after any brain/image roll)

Confirm local-primary is actually carrying the load and Haiku is a rare/zero backstop — off the fleet Grafana
Prometheus (datasource `prometheus`):
```
# brain selection over 24h — expect ~100% local (reason=primary), ~0 haiku (local_down / local_error):
sum by (brain, reason) (increase(operator_brain_selected_total[24h]))
# operator failover cost — expect ≈0. NOTE this is ALL claude-haiku through LiteLLM, not operator-only; the
# operator's attributed Haiku spend is $0 whenever the brain metric above shows 0 haiku selections:
sum(increase(litellm_spend_metric_total{requested_model="claude-haiku"}[24h]))
```
**Healthy** = local carries ~100%, `haiku` selections 0, operator Haiku spend $0. **Flaking** = frequent
`local_down`/`local_error` failover or non-zero operator Haiku spend → chase rogueone/Ollama (VRAM contention / model
not fully on GPU — see the troubleshooting block above). Also glance at the pod's restart count while you're here.
**Validated 2026-08-06** (v20, ~1.5 days post-deploy): 3/3 local-primary, **0 failover**, operator Haiku **$0**
(fleet-wide Haiku was $0.157 from *other* consumers, not the operator) — design behaved.

## Reference
Design: `../design/operator-agent-design.md`. Bake-off: [demos/brain-bakeoff.md](../demos/brain-bakeoff.md).
Guard service: [runbooks/guardrails.md](guardrails.md). Demo: [demos/operator.md](../demos/operator.md). See [[b66-operator-brain-bakeoff]].
