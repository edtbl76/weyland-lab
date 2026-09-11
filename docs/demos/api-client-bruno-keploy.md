# Demo: Bruno (API client) + Keploy (API-regression) (B104)

Two $0/OSS, Git-native API tools. **Bruno** = a hand-authored, assertion-driven client (collections as
committed `.bru` files). **Keploy** = record real API traffic → committed regression test-sets that
`keploy test` replays and diffs. Both complement the machine-readable API-lifecycle catalog (`apis.yaml`,
B155) + contract-lock (B152) — those govern; these exercise. Full commands + gotchas:
[../runbooks/api-client-bruno-keploy.md](../runbooks/api-client-bruno-keploy.md).

## Bruno — CLI run + desktop eyes-on

Collection `bruno/weyland/` — 27 requests / 58 assertions across 9 services (tool-server boundary incl.
all 5 vector backends + a functional retrieval POST · LiteLLM gateway · Qdrant · Weaviate · Neo4j · Ollama
· rag-embed · ClickHouse · MLflow gateway). Scope bounds in the collection README.

**CLI walkthrough (RUN 2026-09-10, live vs the LAN services):**
```
cd bruno/weyland
npx --yes @usebruno/cli run tool-server gateway qdrant weaviate neo4j ollama rag-embed clickhouse mlflow-gateway --env lan
#   → 26 requests, 56 assertions, all green
npx --yes @usebruno/cli run authenticated --env lan --env-var gw_key=$LITELLM_API_KEY
#   → 1 request, 2 assertions, green (total 27 / 58)
```

**UI walkthrough + UAT (RUN 2026-09-10, eyes-on):** open `bruno/weyland` in the Bruno **desktop app** →
environment **lan** → Send. Confirmed `tool-server/health` (200, `status:ok`), `tool-server/status`
(`llm.status:ok`), `qdrant/collections` (real list), `tool-server/context-search` (POST → `results[]`) all
render + assert green. **Gotcha (recorded):** the Bruno **snap** renders its file dialogs as **tofu (□)** —
its confined 2018-era `gnome-3-28-1804` GTK platform can't resolve host fonts (the system fonts are fine;
only the snap tofus). **Fix: use the unconfined `.deb`/AppImage (v4.1.0), not the snap** — then it renders
normally. Steps in the runbook.

## Keploy — record → replay (RUN 2026-09-10, `verified_green`)

Recorded the `golden-python-fastapi` golden path and replayed it: **`keploy test` → 7/7 pass,
dependency-free (`verified_green`)**. Corpus committed at `keploy/keploy/golden-fastapi-smoke/` (config +
mappings + 7 tests; **no `mocks.yaml`** — no downstream deps; reports gitignored).

**The negative cases are part of the demo — keploy caught real problems on the way to green:**
- **Ray collision** — replay returned a `WSGIServer/Python-3.11.14` metrics body for every request instead
  of the app's `uvicorn`/Python-3.12 responses. Cause: Ray owns rogueone `:8080` (dashboard **and**
  metrics); the app was on 8080. Fix: move the app to **8091**. *(keploy correctly flagged the wrong
  responses — that IS the tool working.)*
- **Port remap** — a host≠container remap (18091→8091) broke keploy's readiness probe + replay routing;
  fix was **same-port** 8091:8091.
- **Readiness hang** — the default probe hits a reserved path the golden app 404s → keploy waits out its
  3-minute timeout. Fix: `--health-path /health` (also `healthPath` in `keploy.yml`).

**On-demand, on the host:** `bash scripts/keploy-verify.sh` (rogueone — needs docker + keploy). **CI note
(TESTED, pipeline #115):** keploy can NOT run in a k3s step pod — it needs **Docker** (its installer
refuses without it; it runs its agent inside a docker container), and k3s step pods have containerd, no
docker. It was *not* the eBPF/privileged worry (privileged pods run fine here). The CI path, if ever worth
it, is a local-backend workflow on rogueone — see [../runbooks/woodpecker-step-menu.md](../runbooks/woodpecker-step-menu.md).

## Cleanup

Bruno + the keyless keploy checks are read-only. Keploy record works in a throwaway app container it
removes (`--rm`); the committed corpus (`tests/` + `config.yaml` + seed) is the deliverable; `mocks.yaml`
and `reports/` are gitignored.
