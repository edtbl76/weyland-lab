# weyland-postgres — query cookbook

**Connect:** `weyland-postgres.weyland.svc.cluster.local:5432` (ns `weyland`, image `pgvector/pgvector:pg16`).
Superuser `weyland`, default DB `weyland`. In-pod:
`kubectl -n weyland exec -it deploy/weyland-postgres -- psql -U weyland weyland`.
IntelliJ/DataGrip → PostgreSQL driver against `127.0.0.1:5432` after **port-forwarding the svc via the k8s
plugin** (Services → `weyland-postgres` → Forward Ports). **STRICT mTLS** — the pod is meshed (Istio sidecar,
`appProtocol: tcp`); any *in-cluster* client must join the mesh or the connection dies with an opaque
`ECONNRESET`. Password lives in `weyland-postgres-secret/POSTGRES_PASSWORD` (env `WEYLAND_PG_PASSWORD`) —
never hardcode it.

This is the **general platform Postgres** — it backs many services, each in its own DB:
`weyland`, `dagster`, `mlflow`, `nessie`, `lakefs`, `datahub`, `keycloak`, `feast`, `sonarqube`, `glitchtip`,
`unleash`. Most are app-owned plumbing (state stores) — this cookbook covers the two **data-relevant** DBs:
`weyland` (the RAG corpus + the LLM-eval harness) and `feast` (the feature store's offline source tables).
The full MusicBrainz mirror is a **separate, dedicated** Postgres — see **[[musicbrainz-postgres]]**, not here.

### List the databases
```sql
\l                                    -- every DB on the instance (weyland, feast, dagster, mlflow, …)
-- or, without psql meta-commands:
SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;
```

---

## `weyland` DB — RAG corpus (pgvector)

The retrieval store the tool-server queries. `rag_documents` (one row per source file) → `rag_chunks`
(chunked text + its `embedding vector(384)`, from `BAAI/bge-small-en-v1.5`). Two corpora share the tables:
the docs/code run and the AIDLC knowledge base (`source_path LIKE 'aidlc-kb/%'`, B37).
```sql
\c weyland
\dt                                   -- rag_documents, rag_chunks, eval_*, plus app tables
-- shape of the corpus
SELECT source_type, count(*) AS docs FROM rag_documents GROUP BY source_type;   -- markdown | code
SELECT d.name, count(c.*) AS chunks
FROM rag_documents d JOIN rag_chunks c ON c.document_id = d.id
GROUP BY d.name ORDER BY chunks DESC LIMIT 20;

-- the AIDLC-KB corpus vs the docs/code corpus
SELECT CASE WHEN source_path LIKE 'aidlc-kb/%' THEN 'aidlc-kb' ELSE 'docs/code' END AS corpus,
       count(*) AS documents
FROM rag_documents GROUP BY corpus;
```

### pgvector similarity search
Cosine distance (`<=>`); `1 - distance` = similarity. Embed your query with the **same** `bge-small-en-v1.5`
(384-dim, unit-normalized) — this is exactly what the tool-server's `/context/ask` does under the hood. Paste a
literal vector, or in practice let the tool-server embed for you.
```sql
-- top-5 chunks nearest a query vector :q  (:q is a '[0.1,-0.2,…]'::vector, 384 dims)
SELECT d.name, c.chunk_index, 1 - (c.embedding <=> :q) AS score, left(c.content, 200) AS preview
FROM rag_chunks c JOIN rag_documents d ON d.id = c.document_id
WHERE c.embedding IS NOT NULL
ORDER BY c.embedding <=> :q
LIMIT 5;

-- self-similarity: chunks most like a chunk you already have (dedupe / neighborhood probe)
WITH seed AS (SELECT embedding FROM rag_chunks WHERE id = 1)
SELECT d.name, c.chunk_index, 1 - (c.embedding <=> seed.embedding) AS score
FROM rag_chunks c JOIN rag_documents d ON d.id = c.document_id, seed
WHERE c.id <> 1
ORDER BY c.embedding <=> seed.embedding LIMIT 10;
```

## `weyland` DB — LLM eval harness (B4)
The RAG leaderboard tables (see `scripts/eval-schema.sql`, runbook **[[eval-harness]]**). One `eval_runs` row per
leaderboard execution → `eval_questions` (ragas-generated) → `eval_results` (one answer per question × model) →
`eval_scores` (judge-**panel** LLM-as-judge, ≥3 judges × 3 metrics per result). `eval_leaderboard` is a view
that averages across judges.
```sql
-- the leaderboard for the latest scored run (avg over the judge panel), pivoted-ish
SELECT model, metric, round(avg_score::numeric, 3) AS avg_score, scored_n
FROM eval_leaderboard
WHERE run_id = (SELECT max(id) FROM eval_runs WHERE status = 'scored')
ORDER BY metric, avg_score DESC;

-- overall winner: mean of the three metrics per model, latest run
SELECT model, round(avg(avg_score)::numeric, 3) AS mean_score
FROM eval_leaderboard
WHERE run_id = (SELECT max(id) FROM eval_runs WHERE status = 'scored')
GROUP BY model ORDER BY mean_score DESC;

-- did any judge disagree wildly? per-judge spread on one metric (the single-judge-noise check)
SELECT r.model, s.judge, round(avg(s.score)::numeric, 3) AS avg_faithfulness
FROM eval_results r JOIN eval_scores s ON s.result_id = r.id
WHERE r.run_id = (SELECT max(id) FROM eval_runs) AND s.metric = 'faithfulness'
GROUP BY r.model, s.judge ORDER BY r.model, avg_faithfulness DESC;

-- run history
SELECT id, created_at, status, question_count, array_length(models,1) AS n_models FROM eval_runs ORDER BY id DESC;
```
> Also in `weyland`: `scripts/guardrail-schema.sql` and `scripts/model-catalog-schema.sql` tables (guardrail
> events, model registry) — same instance, same access pattern; introspect with `\dt` and adapt the above.

---

## `feast` DB — feature-store offline sources

The two Postgres tables Feast reads as its **offline store** (registry+offline = this DB; online = Valkey). Loaded
from the dbt marts by `scripts/feast_setup.py` (`if_exists='replace'`), then `feast apply` + `materialize`. You
normally *serve* these through Feast (**[[feast]]**) — query them directly here only to inspect the raw source.
```sql
\c feast
\dt                                   -- track_audio_features, state_health_risk (+ feast's own registry tables)

-- track_audio_features: entity `track_id` + 11 Spotify audio features + a synthetic event_timestamp (static)
SELECT track_id, danceability, energy, valence, tempo FROM track_audio_features LIMIT 10;
SELECT count(*) AS tracks, round(avg(danceability)::numeric,3) AS avg_dance,
       round(avg(energy)::numeric,3) AS avg_energy FROM track_audio_features;

-- state_health_risk: entity `state`, event_timestamp = BRFSS survey year; crude-prevalence % of 4 conditions
SELECT state, event_timestamp::date AS year, diabetes_pct, asthma_pct, copd_pct, depression_pct
FROM state_health_risk ORDER BY diabetes_pct DESC LIMIT 15;

-- highest-diabetes state per survey year (the time-varying, point-in-time-shaped view)
SELECT DISTINCT ON (event_timestamp) event_timestamp::date AS year, state, diabetes_pct
FROM state_health_risk ORDER BY event_timestamp, diabetes_pct DESC;
```

---

## weyland-postgres-isms worth knowing
- **One instance, many DBs** — `\c <db>` to switch; a query only sees the DB you're connected to. The DataHub
  postgres source ingests *every* DB, which is why its recipe runs as the `weyland` superuser.
- **STRICT mTLS** is the #1 gotcha: an in-cluster client that isn't meshed gets a bare `ECONNRESET`, not an auth
  error. Mesh it (sidecar inject) or reach it from IntelliJ over the k8s port-forward. See
  **[[postgres-strict-needs-mesh]]** · **[[feedback-intellij-k8s-portforward]]**.
- **`Recreate` deploy strategy** — single-instance on RWO storage; don't `rollout restart` casually
  (**[[k8s-rwo-recreate-strategy]]**).
- **pgvector** ships in the `pgvector/pgvector:pg16` image (`CREATE EXTENSION vector`); `<=>` cosine, `<->` L2,
  `<#>` inner product. Same 384-dim `bge-small-en-v1.5` vectors live in **[[qdrant]]** / **[[weaviate]]** /
  **[[lancedb]]** — pgvector is the RAG default backend.
- The `feast` tables are **replaced** on every `feast_setup.py` run (sourced from the dbt marts, **[[dbt-marts]]**)
  — treat them as derived, not authoritative; the marts are the source of truth.
- The full MusicBrainz mirror is **not** here — dedicated instance, own cookbook: **[[musicbrainz-postgres]]**.
