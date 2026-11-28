# golden-paths-shared/node — code every Node golden path shares (B262)

The SOURCE of the framework-neutral parts of deep contract v2 for `node/express`, `node/fastify` and `node/nestjs`.
Each path that holds a `.golden-shared` marker gets a synced copy, headed `// GENERATED ...` (ADR-0020, owner decision
"One source, synced copies"). Edit here, then run `bash /home/edwardmangini/IdeaProjects/weyland/scripts/sync-golden-shared.sh`;
the `repo-guards` CI step runs it with `--check` and fails on any drifted copy.

| File | What |
|---|---|
| `src/shared/items-store.js` | the async `ItemStore` interface and `InMemoryItemStore`, the default (C7) |
| `src/shared/settings.js` | `loadSettings()`: `GOLDEN_GREETING`, validated at startup (C6) |
| `src/shared/items-backends.js` | Postgres (pg), Valkey (ioredis), Redpanda (kafkajs) and MinIO (@aws-sdk/client-s3) adapters and `buildStoreFromEnv()` |
| `src/shared/tracing.js` | `setupTracing()`: an OTel span per request when `OTEL_EXPORTER_OTLP_ENDPOINT` is set, a no-op otherwise (C11) |
| `src/shared/v2-smoke.cjs` | the v2 smoke sequence each path's `.smoke` runs against its own server |
| `integration/items-backends.integration.js` | the adapters against real backends; the `integration-node` CI step runs it |

The integration clients are each path's `devDependencies` (never in an image). A scaffolded service that uses a backend
moves that client into `dependencies`. Design: `docs/concepts/golden-path-capabilities.md`.
