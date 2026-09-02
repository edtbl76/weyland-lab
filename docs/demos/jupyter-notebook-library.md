# Demo — JupyterHub notebook library (B81)

The L8 notebook layer of the mesh as a **semi-exhaustive, runnable library**: 25 numbered notebooks
plus the `datasets_lake` seed, spanning formats to storage to query to vector/graph to transform/semantic
to feature/ML to AI/RAG to governance/quality to streaming — each runs end-to-end against the live mesh,
and that IS the test (DoD). Distribution is git-sync on spawn, not an image rebuild. **Executed + eyes-on
2026-09-02** — the full 26-notebook library ran clean headless IN-POD (Keycloak-spawned singleuser pod).

- **Runbook:** [runbooks/jupyterhub.md](../runbooks/jupyterhub.md) — esp. §4 (the library) + §5 (the operator spawn-verify UAT checklist)
- **Library index:** `k8s/jupyterhub/singleuser/notebooks/README.md` (git-synced into `~/notebooks`)
- **Backlog:** B81 (Linear EMA-71), thread (b) of the [B78] data-mesh maturity bucket; also satisfies **U16** (nb 31 Weaviate)

## UI walkthrough (eyes-on — a UI is the deliverable)

1. **Spawn a server** — browse `https://jupyter.weyland.lab` → **Keycloak login** (weyland realm, OIDC) →
   JupyterHub spawns a per-user singleuser pod.
   **UAT — confirm:**
   - The spawn **pulls `registry.weyland.lab/weyland-jupyter:v1`** from the in-cluster registry (a few
     seconds; `pullPolicy: IfNotPresent`, prune-safe — see the runbook §3 `ErrImageNeverPull` gotcha).
   - JupyterLab opens at `/lab`.
   - `~/notebooks` is **populated by the postStart git-sync**: 25 numbered notebooks + `datasets_lake.ipynb`
     + `README.md` (the library == `main`; edits inside `~/notebooks` are overwritten on respawn, git is the
     source — do scratch work in `~/scratch/`, which the home PVC persists).
2. **Open the library index** — open `README.md` (rendered) and read the layer tables (formats → storage →
   query → vector/graph → transform/semantic → feature/ML → AI/RAG → governance/quality → streaming).
   **UAT — confirm:** every notebook listed in the index is present in the file browser.
3. **Open 2-3 notebooks and Run All** — e.g. `20_query_trino_federation`, `31_vector_weaviate`,
   `81_streaming_cdc_debezium`.
   **UAT — confirm:** each notebook **Run All Cells → 0 error outputs**, and cells render real results
   (tables / plots) — the federated `iceberg.eval ⋈ postgresql` join returns rows, Weaviate vector/BM25/hybrid
   search returns objects, the CDC notebook shows the connector RUNNING + the Iceberg mirror.
4. **The meshed-store notebooks** — open `21_query_duckdb_gizmosql`, `22_query_tier2_native`,
   `41_semantic_cube` and Run All.
   **UAT — confirm:** all three run clean. These are the mesh-join proof: GizmoSQL (nb 21), MySQL (nb 22),
   and Cube (nb 41) are reached over mTLS, which only works because the singleuser pod carries the
   `istio-proxy` sidecar (`extraLabels` → `sidecar.istio.io/inject: "true"`). If any of the three hangs, the
   sidecar did not inject — re-check the runbook §5.1 sidecar box.

Confirm the sidecar directly (from mother/kubectl):
```
kubectl -n jupyterhub get pod -l component=singleuser-server -o jsonpath='{.items[0].spec.containers[*].name}'
```
Expected: `notebook istio-proxy` (both containers present).

## CLI walkthrough (the whole-library batch test — the anti-fabrication test)

This is the test that makes fabrication impossible: run every notebook headless from inside the real
singleuser pod, one PASS/FAIL line each. In the **JupyterLab terminal** (inside the singleuser pod, so it
has the injected env + in-cluster DNS + can `%pip`):

```
cd ~/notebooks && for nb in $(ls [0-9]*.ipynb datasets_lake.ipynb 2>/dev/null); do jupyter nbconvert --to notebook --execute --stdout "$nb" >/dev/null 2>&1 && echo "PASS  $nb" || echo "FAIL  $nb"; done
```

`--stdout >/dev/null` runs without modifying the files; a cell error makes nbconvert exit non-zero → `FAIL`.
Takes several minutes (some notebooks `%pip install` per run; `60` downloads bge-base ~440 MB once).

Expected: **26 × PASS**:
```
PASS  01_format_parquet.ipynb
PASS  02_format_arrow_ipc.ipynb
PASS  03_format_avro.ipynb
PASS  04_format_lance.ipynb
PASS  10_storage_lakefs.ipynb
PASS  11_storage_nessie_iceberg.ipynb
PASS  20_query_trino_federation.ipynb
PASS  21_query_duckdb_gizmosql.ipynb
PASS  22_query_tier2_native.ipynb
PASS  30_vector_qdrant.ipynb
PASS  31_vector_weaviate.ipynb
PASS  32_vector_lancedb.ipynb
PASS  33_graph_neo4j.ipynb
PASS  40_transform_dbt_marts.ipynb
PASS  41_semantic_cube.ipynb
PASS  50_feature_feast.ipynb
PASS  51_ml_mlflow.ipynb
PASS  60_rag_llamaindex.ipynb
PASS  61_gateway_litellm.ipynb
PASS  62_eval_rag.ipynb
PASS  70_governance_datahub.ipynb
PASS  71_quality_soda.ipynb
PASS  72_authz_ranger.ipynb
PASS  80_streaming_redpanda.ipynb
PASS  81_streaming_cdc_debezium.ipynb
PASS  datasets_lake.ipynb
```

For any `FAIL`, get the traceback:
```
jupyter nbconvert --to notebook --execute --stdout <nb> 2>&1 | tail -40
```
A `FAIL` on `21`/`22`/`41` means the mesh-join regressed; on `60` means git-sync/public egress; on a creds
notebook means its sealed secret is missing from the `jupyterhub` ns.

**Known gap (still a PASS):** `51_ml_mlflow`'s model-LOAD cell catches its missing artifact creds and prints
a graceful note rather than erroring, so nbconvert exits 0. This is deliberate — loading the model blob from
`s3://mlflow/` needs MinIO artifact creds that boto3 reads as generic `AWS_*`, which would collide across
every notebook kernel and widen every spawn's blast radius (see runbook §4 DECISION + §5 nb 51 box). The
surrounding value (experiments / runs / registry browse) works in-pod regardless.

### Pre-flight (from mother/kubectl, before spawning)

The ten `jupyterhub`-ns secrets the notebooks draw from must all exist:
```
kubectl -n jupyterhub get secret jupyterhub-oidc lakefs-creds iceberg-s3-creds gizmosql-creds tier2-creds neo4j-creds cube-creds mlplat-creds litellm-creds datahub-creds
```
Expected: all ten present. And Argo `jupyterhub` app **Synced/Healthy** (the live `jupyterhub-values.yaml`
carries the `extraLabels` mesh-join + every `extraEnv`).

## Teardown / cleanup

**Read-only by default.** The batch above runs with `--stdout >/dev/null`, so it does not modify the notebook
files, and most notebooks are read-only against the live mesh. The few that write are **self-cleaning**:

- `10_storage_lakefs` — creates scratch lakeFS branches, **deleted** in its cleanup cell (leaves only `main`; the assert passes).
- `11_storage_nessie_iceberg` — creates a scratch `nb_demo` Iceberg namespace, **dropped** in its cleanup cell (the assert passes).
- `33_graph_neo4j` — creates a transient GDS graph projection, **dropped** after use.

**Intentional persistent state:** `81_streaming_cdc_debezium` left a persistent `bravo-v3` row in the
`cdc_demo` demo table (id 11, `bravo-v2`→`bravo-v3`), produced by a one-row UPDATE to
`musicbrainz_db.public.cdc_demo` so the consume cell shows a real live `op=u` envelope. This is documented and
by design (runbook §4); to refresh, UPDATE a `cdc_demo` row and re-run the notebook.

Scratch work in `~/scratch/` persists on the 2 Gi home PVC; anything edited inside `~/notebooks` is replaced
by git-sync on the next spawn. **Idle singleuser pods cull to zero** after 1h — the spawn cost is paid only
while a notebook session is open; hub + proxy stay tiny and always-on.
