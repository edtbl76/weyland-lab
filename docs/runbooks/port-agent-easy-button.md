# Port actions → cluster (port-agent + store-scaler)

**What:** the execution path that lets a **Port self-service action** act on the LAN cluster. Built
2026-07-02 for a store wake/sleep button, but the plumbing is **reusable** for any "click a Port button →
do X in the cluster" (restart a service, kick a Dagster job, run a one-off).

**Why it's non-trivial:** Port is SaaS (EU org `org_KyCTEN4PVUv1D3TM`) and the lab is LAN-only — Port's cloud
**cannot reach inbound** (same wall as GitHub push webhooks). The self-hosted **port-agent** solves it by
connecting **outbound** to Port and polling for action runs.

## Architecture

```
Port UI "Scale data-mesh store" (dropdowns: store + wake/sleep)
   → Port cloud
   → port-agent          [ns port-agent, Helm port-labs/port-agent, outbound POLLING]
   → POST {store, action} → store-scaler        [data-mesh, FastAPI]
   → store-scaler patches deployments/scale      [least-priv store-scaler SA]
```

- **port-agent** — `k8s/port-agent/port-agent-values.yaml`, Argo app `port-agent` in `helm-apps.yaml`.
  Creds via existing Secret `port-agent-creds` (ns `port-agent`, keys `PORT_CLIENT_ID`/`PORT_CLIENT_SECRET`),
  created out-of-band (never committed).
- **store-scaler** — `services/store-scaler/` (image `store-scaler:local`, built + `ctr import` on mother),
  `k8s/data-mesh/store-scaler.yaml` + `store-scaler-rbac.yaml`. Reads the action payload, validates against an
  allowlist, patches `deployments/scale`. Uses in-cluster SA (native k8s auth), sidecar disabled so the
  cross-namespace agent call is plain HTTP.
- **The action** — `tofu/port/actions.tf` (`port_action.scale_data_mesh_store`).

## The gotcha chain (each one cost a debugging loop)

1. **`STREAMER_NAME: POLLING`, not `KAFKA`.** This org has no Kafka creds provisioned → KAFKA mode crashloops
   on `get_kafka_credentials → None`. Any non-KAFKA value selects the PollingStreamer (polls the Port API every
   ~10s — so the button has ~10s latency, not instant). No Kafka/consumer-group config needed.
2. **EU org → `PORT_API_BASE_URL: https://api.port.io`.** The agent defaults to the legacy US URL
   `api.getport.io`, where `claim-pending` returns **403** (runs are region-pinned). US region would be
   `api.us.port.io`. Metadata/tofu route cross-region on getport.io; run-claiming does not.
3. **ORGANIZATION credentials, not Personal.** Personal creds (Client ID = your **email**) authenticate and
   manage the catalog (the tofu provider uses them fine) but **403 on `/v1/actions/runs/claim-pending`** —
   claiming org run execution is org-scoped. Use the creds from Port → **Credentials → Organization** tab.
   Rule of thumb: **403 (not 401)** = authenticated but not authorized → it's a region/permission problem,
   never a wrong password.
4. **The action needs a `body`.** Without `webhook_method.body`, Port forwards only the invocationMethod stub
   and the user inputs never leave Port (arrive `null`). Template them in — Port merges the resolved body into
   the message **root**:
   ```hcl
   webhook_method = {
     url = "http://store-scaler.data-mesh.svc.cluster.local/scale"; method = "POST"; agent = true
     body = jsonencode({ store = "{{ .inputs.store }}", action = "{{ .inputs.action }}" })
   }
   ```
5. **Agent `controlThePayloadConfig` body `"."`** forwards the whole message; the receiver recursively finds
   the inputs (a dict holding both expected keys) so it's robust to however the polling message nests things.
6. **Helm config change ≠ pod restart.** After Argo syncs a values change, `rollout restart deploy/port-agent`
   to remount the new `controlThePayloadConfig` — the agent loads it once at startup.

## Adding a new Port → cluster action

1. Add a `port_action` in `tofu/port/actions.tf` with the inputs and a `webhook_method` (`agent = true`, a
   `body` that templates the inputs). `url` points at your receiver.
2. Point it at an in-cluster receiver — reuse `store-scaler` (extend its allowlist/logic) or add a sibling
   service with a scoped SA.
3. If the agent should route it, no agent change is needed (`body: "."` forwards everything; enable per-action
   filtering with an `enabled` JQ on the action identifier once there's more than one).
4. `source tofu/port/.env && tofu -chdir=… apply`.

## PARKED: the sleep half (GitOps conflict)

The button **works** end-to-end (verified: sleep gizmosql → `replicas=0`, HTTP 200), but the sleep **doesn't
stick**: the `data-mesh` Argo app (`selfHeal: true`) sees `replicas: 0` diverge from the manifest's
`replicas: 1` and reverts it within ~3 min. Scaler and Argo fight; Argo wins.

The standard fix is `ignoreDifferences` on `/spec/replicas` (+ `RespectIgnoreDifferences=true`) for the four
idle stores on the `data-mesh` Application — cede that one field to the scaler. It was written then **reverted**
pending a decision to possibly drive scaling via **KEDA inside Argo**. Note: **KEDA hits the same conflict**
(KEDA+Argo still needs the `/spec/replicas` carve-out) and KEDA's triggers are cron/metric/event, not a button.
So the carve-out is unavoidable if you want the button sticky; KEDA just changes who pulls the trigger.

**Decision when resumed (updated 2026-08-22):** **KEDA has been RETIRED** — it needed the same
`/spec/replicas` carve-out, so the autonomous-policy branch below is no longer on the table without
reinstalling it. The carve-out itself was re-examined and **rejected on mechanism**: `ignoreDifferences`
is unscoped and permanent, so a sleeping store would report Synced/Healthy, the accidental-scale-to-zero
safety net would vanish, and the sleep state would live only in the cluster (the B137 disease).
**If store sleep is wanted, the clean form is `replicas: 0` committed to GIT** — Argo enforces it, the
repo stays truthful, drift detection keeps working, and a rebuild restores intent. The Port button would
write to git rather than the cluster.

*Original options, for the record:* manual button → keep store-scaler + add the `ignoreDifferences`
carve-out; autonomous policy (idle-timeout / overnight) → KEDA + `managedFieldsManagers` ignoreDifferences. The RAM the
sleep reclaims (~1–1.5 GB) is marginal now that the real OOM (Dagster ingestion) is fixed — the **execution
plumbing** is the keeper, not the sleep feature.

See also: `docs/schedules.md`, [argocd.md](argocd.md), [keda.md](keda.md).
