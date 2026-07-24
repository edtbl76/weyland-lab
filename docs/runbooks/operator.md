# Operator agent — the `weyland-operator` service (B66)

Text the lab from anywhere → it acts. A LangGraph ReAct agent (`gpt-oss:20b`) over the tool-server's read + act
tools, fronted by **Telegram long-poll**, with **per-chat Postgres session memory** and an **app-level confirm-step**
on every state-changing action. This is the operator lane **Hermes vacated** (CT-104 destroyed 2026-07-23) — a k8s pod
on mother, not an LXC. `weyland-operator.weyland.svc:8080` (ClusterIP, no ingress — long-poll is outbound).

## The three parts (as built)
1. **Agent core** — `create_react_agent(gpt-oss, tools)`; read tools (`status`, `context_search`, `context_ask`)
   called freely; native tool-calling (bake-off-proven). `POST /operator/ask {message}` is the stateless test/probe
   surface.
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
- **Four independent rails:** (1) Telegram **allowlist** (`TELEGRAM_ALLOWED_USERS`) · (2) **confirm-step**
  (app-fires-on-yes) · (3) `act.py` **fail-closed** `JOB_ALLOWLIST` (unknown tool/job refused before any HTTP) ·
  (4) the tool-server's own **`Hook.ACT`** guard on the launch. Any one holding is enough.
- Acts are **Telegram-only** (the confirm needs a session). `/operator/ask` surfaces a proposal but never fires.
- The 3 acts → the tool-server's `/mcp-act` jobs: `pipeline_trigger` (`job_name` ∈ `weyland_ingestion_job` /
  `weyland_eval_job` / `weyland_eval_score_job`), `evals_run`, `evals_score`. Actor audit = `operator:telegram:<chat_id>`.

## Architecture decisions (see the B66 design doc)
- **Brain = local `gpt-oss:20b`** (Ollama on rogueone) — the bake-off found it *ties Claude Haiku* on tool-selection,
  the full loop, and the act-path safety test (8/8, declined every trap), faster and $0. **Haiku (API) = documented
  fallback**, reached by repointing `OLLAMA_BASE_URL`/`MODEL` — no paid path wired ($0 budget). See [[b66-operator-brain-bakeoff]].
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
- **Registry gotcha (B101):** confirm `curl -s https://registry.weyland.lab/v2/weyland-operator/tags/list` shows `vN`
  before bumping `k8s/weyland-operator/deployment.yaml`; the manifest PUT often doesn't finalize on the first push.
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

## Reference
Design: `aidlc-docs/construction/operator-agent-design.md`. Bake-off: [demos/brain-bakeoff.md](../demos/brain-bakeoff.md).
Guard service: [runbooks/guardrails.md](guardrails.md). Demo: [demos/operator.md](../demos/operator.md). See [[b66-operator-brain-bakeoff]].
