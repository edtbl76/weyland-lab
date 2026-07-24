# MLflow — runbook (B10+B16)

Experiment tracking + model registry at `mlflow.weyland.lab` (Keycloak SSO via `traefik-forward-auth`). Reuses the shared **Postgres**
(backend store) and **MinIO** (artifact store — **two-plane**: small artifacts proxied, big models direct) — fits the lab's reuse ethos.

> **B47 upgrade (2.18 → 3.14).** MLflow 3.x replaces the Flask/gunicorn server with **FastAPI/uvicorn**.
> The Postgres backend schema was migrated with **`mlflow db upgrade <backend-store-uri>`** (run once
> against the `mlflow` db). The 3.x server needs an explicit **`--allowed-hosts`** (host allow-list; set
> to the LAN/ingress hosts or the API 400s on `Host`), and the pod memory `limits` were raised to **4Gi**
> (3.x boots heavier — the old 1Gi OOM'd on start).

- Manifest: `k8s/mlflow/mlflow.yaml` (Middleware + Deployment + Service + Ingress).
- Backend store: Postgres `mlflow` db owned by the `mlflow` role.
- Artifact store: MinIO `mlflow` bucket. **Two-plane:** small artifacts proxy **through** MLflow (`--serve-artifacts`); **big models upload DIRECT to MinIO** (experiment `artifact_location=s3://mlflow/…`) because the proxy times a multi-GB `model.pkl` out through the 1Gi pod. See [remote-training.md](remote-training.md) / [mlflow-training.md](mlflow-training.md).
- **Meshed:** the pod carries `sidecar.istio.io/inject: "true"` — STRICT-mTLS Postgres resets a non-meshed client (`read ECONNRESET`). See [[postgres-strict-needs-mesh]].

## Deploy (first time)
Postgres db + role, secrets, bucket, then apply:
```
kubectl exec -n weyland deploy/weyland-postgres -- psql -U weyland -c "CREATE ROLE mlflow LOGIN PASSWORD 'weyland_dev_password';"
kubectl exec -n weyland deploy/weyland-postgres -- psql -U weyland -c "CREATE DATABASE mlflow OWNER mlflow;"
kubectl create secret generic mlflow-secret -n weyland --from-literal=POSTGRES_USER=mlflow --from-literal=POSTGRES_PASSWORD=weyland_dev_password
kubectl create secret generic mlflow-auth -n weyland --from-literal=users="admin:$(openssl passwd -apr1 weyland_dev_password)"
mc mb weyland/mlflow
kubectl apply -f k8s/mlflow/mlflow.yaml && kubectl rollout status deploy/mlflow -n weyland
```

## Smoke test (no installs)
```
kubectl exec -n weyland deploy/mlflow -- python -c "import mlflow; mlflow.set_tracking_uri('http://localhost:5000'); mlflow.set_experiment('smoke'); r=mlflow.start_run(); mlflow.log_param('p',1); mlflow.log_metric('m',0.5); open('/tmp/a.txt','w').write('hi'); mlflow.log_artifact('/tmp/a.txt'); mlflow.end_run(); print('OK', r.info.run_id)"
```
`OK <run_id>` + a file under `mc ls --recursive weyland/mlflow/` + the run in the UI = full stack good.

## GenAI Tracing (B100 Phase 1)
MLflow 3.x **Traces** capture per-step GenAI observability (prompt / retrieved context / tool calls / answer spans) —
the one pane the mesh traces (Tempo) can't give. Live-surface coverage:

| Surface | How | Experiment |
|---|---|---|
| `weyland-agent` (B70) | `mlflow.langchain.autolog()` + `mlflow.llama_index.autolog()` (LangGraph loop + retrievers) | `agentic-rag` |
| `weyland-operator` (B66) | `mlflow.langchain.autolog()` (ReAct loop + tools) | `operator` |
| tool-server `/context/ask` (B100) | **manual spans** — the RAG generate is a raw `httpx`→Ollama call (not a LangChain/OpenAI client) so autolog can't see it: a `context_ask` parent + `retrieve` / `generate` children | `tool-server-rag` |
| eval harness | → **B84** (batch, ~360 traces/run — folds into the eval-observability theme) | — |

- **Fail-safe everywhere:** tracing degrades to a no-op if MLflow is unreachable — observability never takes an
  answer offline (the tool-server wraps each span in a try/except; the agent/operator guard the autolog init).
- **`mlflow.langchain.autolog()` needs the full `langchain` package** in the image (langchain-openai/langgraph pull
  only `langchain-core`) — the tool-server instead uses **`mlflow-skinny`** (manual tracing only, no autolog, lighter).
- Verify a surface's traces (swap `<svc>`/`<exp>`):
  `kubectl -n weyland exec deploy/<svc> -- python -c "import mlflow; mlflow.set_tracking_uri('http://mlflow.weyland.svc.cluster.local:5000'); from mlflow import MlflowClient; e=MlflowClient().get_experiment_by_name('<exp>'); print(len(mlflow.search_traces(experiment_ids=[e.experiment_id])))"`

## Prompt Registry (B100 Phase 2)
Inline prompts are promoted to versioned **MLflow Prompt Registry** artifacts — hot-swappable without a redeploy, and
a trace pins the prompt version that produced each answer. Registered prompts (`@production` alias):

| Prompt | Used by | Notes |
|---|---|---|
| `rag_system` | tool-server `/context/ask` **+** weyland-agent generate | one prompt, two services (identical text) |
| `operator_system` | weyland-operator | static |
| `agent_grade` · `agent_reflect` | weyland-agent grade/reflect | templated (`{question}`/`{context}`/`{backend}`/`{others}`) — rendered via `render_prompt`, `str.format` at the call site |

- **Source of truth:** `scripts/register_prompts.py` (the canonical templates). Run it to sync — idempotent (new
  version only on change, then moves `@production`). rogueone's shell python lacks mlflow → run it inside a pod that
  has it: `kubectl -n weyland exec -i deploy/weyland-agent -- python < scripts/register_prompts.py`.
- **Runtime fetch:** each service embeds `prompts.py` — `load_prompt(name, fallback)` (static) / `render_prompt(name,
  fallback, **vars)` (templated). **TTL-cached** (`PROMPT_TTL`, default 300s) so a version bump takes effect within
  the TTL with **no redeploy**; **fail-safe** → last-cached, else the **baked fallback** constant (a registry outage
  never breaks a request). Each service also bakes a matching copy of the text as that fallback.
- **API:** the Prompt Registry moved to the **`mlflow.genai`** namespace in 3.x (top-level deprecated) — both the
  script and `prompts.py` prefer `mlflow.genai.*` with a top-level fallback. `mlflow-skinny` (the tool-server) has it.
- **Hot-swap workflow:** edit the template in `register_prompts.py` → re-run it (new version + alias moves) → services
  serve the new prompt within `PROMPT_TTL`, no rebuild. Confirm with
  `kubectl -n weyland exec deploy/<svc> -- sh -c "cd /app && python -c \"import prompts; prompts.load_prompt('<name>','fb'); print(prompts.loaded_version('<name>'))\""`.

## Gotchas
- **pip-on-start (v1).** The container installs `psycopg2-binary` + `boto3` on every start (no custom image),
  so first/restart boot is ~1–2 min and needs egress. If restarts get slow/flaky, bake a small
  `FROM ghcr.io/mlflow/mlflow:v3.14.0` + `pip install` image and drop the install from the command.
- **No native auth** — access is gated by **Keycloak SSO** via the shared `traefik-forward-auth` Middleware
  (forward-auth → Keycloak, SSO across `*.weyland.lab`), like Kiali. The old `mlflow-auth` basicAuth dev-password
  Middleware is retired/superseded by the forward-auth gate.
- **Clients:** browser UI = `https://mlflow.weyland.lab` (Keycloak SSO). **Programmatic clients can't use the SSO
  ingress** (forward-auth is browser-only) → they use the **LAN NodePort**
  `MLFLOW_TRACKING_URI=http://192.168.1.243:30500` (`mlflow-lan`, unauth). The two-plane artifact path means
  clients **do** need MinIO creds + `AWS_CA_BUNDLE` (mkcert root) for the direct upload to `s3.weyland.lab`.
- **LAN NodePort (`mlflow-lan`, :30500).** Added for the external Ray training worker (svc DNS is cluster-only,
  the ingress is browser-SSO). Unauthenticated MLflow API on the LAN — `externalTrafficPolicy: Local` preserves
  the source IP so a host firewall can pin it to the worker: `sudo iptables -I INPUT 1 -p tcp --dport 30500 ! -s
  192.168.1.230 -j DROP` (on mother; not yet reboot-persistent). See [remote-training.md](remote-training.md).
