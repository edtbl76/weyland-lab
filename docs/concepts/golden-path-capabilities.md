# Golden-path capability coverage — the design pass (B163)

B153 built 48 golden paths (21 + 14 in B160 + 13 in B164) that meet a **minimal** contract: `/health`, `/ready`,
`/metrics`, `/hello`, lane tests, a coverage floor, a buildkit image and a smoke Job. That proves each language's
paved road builds and serves; it does not demonstrate the framework. A service scaffolded today
(`scripts/new-service.sh`) inherits a ~160-line stub. B163 deepens every path so a scaffold inherits a working
example of its framework, and so the lab exercises the whole development loop across many stacks
(owner: "The payoff is mostly integrity and exercising the process of software development over and over").

This page is the **design pass, with no code**: the deep contract, the per-framework idiom catalog, the integration
tier per language ecosystem, the path-set decision and the sub-item breakdown. Linear EMA-220.
Related: [design/golden-paths.md](../design/golden-paths.md) (the minimal contract and the harness).

## The key decision: one deep contract, implemented in each framework's idiom

The minimal contract works because CI checks the **contract**, never the framework. B163 keeps that altitude: a
**deep contract (v2)** that every service path implements with its framework's own modules. The behaviour is
identical across 38 services, so the smoke Job's assertions and the lane-test cases are the same everywhere,
while the code is idiomatic Django, Spring, Axum, Phoenix and so on. The alternative, a free-form "cover the
framework's modules" per path, gives 38 incomparable checklists and no uniform proof; rejected.

### Deep contract v2 (service paths)

| # | Capability | Required behaviour (checked by lane tests AND the smoke Job) |
|---|---|---|
| C1 | **Routing** | `GET /items` (query `limit` 1-100, default 20; `offset` ≥ 0), `GET /items/{id}` (path param), `POST /items` |
| C2 | **Validation + typed binding** | `POST /items` body `{"name": string 1-64, "tags": [string] ≤ 5}` bound to a typed model; a bad body is **422** with per-field errors |
| C3 | **Structured errors** | one envelope for every error: `{"error": {"code": "...", "message": "...", "request_id": "..."}}`; 404 for an unknown id, 422 for validation, 500 for an unhandled exception (a `GET /boom` route in tests only) — never a framework default page |
| C4 | **Middleware** | `X-Request-ID`: echoed if sent, generated if not, present on every response and in the log line; one JSON access-log line per request (method, path, status, duration_ms, request_id) |
| C5 | **Metrics middleware** | per-route `http_requests_total{route,status}` and a latency histogram, on top of the existing `/metrics` |
| C6 | **Config + env** | `GOLDEN_GREETING` (default `hello, weyland`) shapes `/hello`; an invalid value (empty) **fails startup** with a clear message — config is validated, not read lazily |
| C7 | **DI / app context** | an `ItemStore` interface injected through the framework's mechanism; the in-memory implementation is the default, so the path runs with no backend |
| C8 | **Lifecycle** | a startup hook initialises the store; `/ready` answers 503 until it has; SIGTERM drains in-flight requests before exit |
| C9 | **Testing idiom** | the framework's own test client (FastAPI `TestClient`, Spring `MockMvc`, Go `httptest`, Axum `oneshot`, Phoenix `ConnTest`, …), one test per row above |
| C10 | **API description** | an OpenAPI document where the framework produces one natively (FastAPI, Litestar, NestJS, Spring, Quarkus, Micronaut, ASP.NET, Vapor via plugin); elsewhere skipped (B155 captures contracts from these) |
| C11 | **Tracing hook** | OTel spans per request when `OTEL_EXPORTER_OTLP_ENDPOINT` is set; a documented no-op otherwise (the minimal contract's "OTel hook or stub", made real where an SDK exists) |

Every row keeps the minimal contract green; the smoke Job gains one sequence: create → get → list → 404 envelope →
422 envelope → `X-Request-ID` echo. **Frontend and mobile paths** get an adapted v2 (below), not C1-C11.

## Framework idiom catalog (service paths: 38)

How each framework meets C2/C3/C4/C7/C8 natively. "Skip" names a capability the framework has no idiom for, with
the reason; the path still meets the behaviour with plain code, it just has no framework module to show.

| Path | Validation / binding | Errors | Middleware | DI / context | Lifecycle | Skips |
|---|---|---|---|---|---|---|
| python/fastapi | Pydantic models | exception handlers | `@app.middleware` | `Depends` | lifespan | — |
| python/litestar | msgspec / Pydantic DTOs | exception handlers | middleware + guards | `Provide` | on_startup / lifespan | — |
| python/flask | marshmallow schema | `errorhandler` | `before/after_request` | app context + `g` / extension | app factory | DI framework (none native) |
| python/django | DRF serializers | DRF exception handler | Django middleware | apps registry / settings | `AppConfig.ready` | DI (none native) |
| java/spring-boot | Bean Validation `@Valid` | `@RestControllerAdvice` | `OncePerRequestFilter` | Spring beans | `SmartLifecycle`, graceful shutdown | — |
| java/quarkus | Hibernate Validator | `ExceptionMapper` | `ContainerRequestFilter` | CDI | `StartupEvent` | — |
| java/micronaut | `@Valid` + `@Introspected` | `ExceptionHandler` | `@Filter` | compile-time DI | `StartupEvent` | — |
| kotlin/ktor | kotlinx.serialization + RequestValidation plugin | StatusPages | interceptors / plugins | Koin-free: `Application` attributes | `ApplicationStarted` | DI container (not native) |
| scala/http4s | circe decoders | `HttpApp` error handling | `Middleware` | Resource / constructor | `Resource` lifecycle | — |
| clojure/ring | malli / spec | middleware wrapper | ring middleware | component map | `-main` start/stop | DI (none native) |
| clojure/compojure | malli / spec | middleware wrapper | ring middleware | component map | `-main` start/stop | DI (none native) |
| go/nethttp | `encoding/json` + validator func | error writer | `http.Handler` wrapper | constructor injection | `Server.Shutdown` | validation lib (stdlib only) |
| go/gin | binding tags (`validator/v10`) | `c.Error` + middleware | `gin.HandlerFunc` | handler struct | `Shutdown` | — |
| go/echo | `Bind` + `Validator` | `HTTPErrorHandler` | `echo.MiddlewareFunc` | handler struct | `Shutdown` | — |
| go/fiber | `BodyParser` + validator | `ErrorHandler` | `fiber.Handler` | handler struct | `ShutdownWithContext` | — |
| rust/axum | serde + `validator` extractors | `IntoResponse` error type | tower layers | `State` | `with_graceful_shutdown` | — |
| rust/actix | serde + `validator` | `ResponseError` | `wrap` middleware | `web::Data` | `Server` handle | — |
| rust/rocket | `FromForm`/serde guards | catchers | fairings | managed `State` | `Liftoff` fairing | — |
| node/express | zod (validator middleware) | error middleware | `app.use` | closure / factory | `server.close` | DI (none native) |
| node/fastify | JSON Schema (built in) | `setErrorHandler` | hooks (`onRequest`) | decorators / plugins | `onReady`/`onClose` | — |
| node/nestjs | `ValidationPipe` + class-validator | exception filters | middleware + interceptors | modules / providers | `OnModuleInit`, shutdown hooks | — |
| dotnet/aspnet | DataAnnotations / minimal-API filters | `ProblemDetails` → envelope | middleware | built-in DI | `IHostedService`, graceful shutdown | — |
| ruby/rails | strong params + ActiveModel validations | `rescue_from` | Rack middleware | Rails app config | initializers | DI (none native) |
| ruby/sinatra | manual + dry-validation | `error` blocks | `before`/`after` filters | settings | `configure` | DI (none native) |
| php/slim | respect/validation | error middleware | PSR-15 middleware | PHP-DI container | — | lifecycle hooks (per-request runtime) |
| elixir/phoenix | Ecto changesets | `FallbackController` | plugs | application supervision | supervision tree | — |
| elixir/plug | Ecto changesets (schemaless) | `Plug.ErrorHandler` | plugs | supervision | supervision tree | — |
| erlang/cowboy | hand validation | handler errors | cowboy middlewares | supervision | supervision tree | validation lib (none idiomatic) |
| swift/vapor-app | `Validatable` + `Content` | `ErrorMiddleware` | `AsyncMiddleware` | `Application` storage | lifecycle handlers | — |
| dart/shelf | manual + `json_serializable` | middleware | `Pipeline` middleware | closure | `serve` + signal | validation lib |
| haskell/scotty | aeson `FromJSON` | `defaultHandler` | WAI middleware | `ScottyT` reader | `bracket` | — |
| julia/oxygen | StructTypes / JSON3 | middleware | `@middleware` | closure | `serve` hooks | DI (none) |
| perl/mojolicious | `Mojolicious::Validator` | `exception` helper | hooks (`before_dispatch`) | helpers | `hook` before_server_start | — |
| r/plumber | manual | `pr_set_error` | filters | closure | `pr_hooks` | validation lib (none idiomatic) |
| lua/openresty | manual + cjson | `error_page` + Lua | nginx phases (`access_by_lua`) | module tables | `init_worker_by_lua` | DI, validation lib |
| ada/aws | manual | callback errors | AWS dispatchers | packages | AWS server start/stop | DI, validation lib |
| c/libmicrohttpd | manual (cJSON) | manual | request callback | manual | daemon start/stop | DI, validation, middleware (none) |
| cpp/httplib | nlohmann/json | `set_exception_handler` | `set_pre_routing_handler` | manual | `listen`/`stop` | DI, validation lib |

The long-tail rows (dart through cpp) carry the most skips: their frameworks are thin, which is itself what the path
should demonstrate honestly. They meet the behaviour of every row; the skip column only says no framework module exists.

### Adapted v2 for frontend and mobile paths (10)

Frontend (angular, astro, nextjs, react-router, vite-react, vue) and mobile (flutter, react-native, swift-tokamak,
swift-ios) are clients. Their depth is: **routing** (a list and a detail route with a param), **forms + validation**
(a create-item form with field errors), **data fetching** against the deep contract's `/items` with loading, empty
and error states (the error envelope rendered), **state** (the framework's idiom: signals, stores, hooks, providers),
and **component tests** in the framework's runner. Their API calls are tested against a recorded contract fixture of
the deep contract; they have **no integration tier** (they own no backend). swift-ios stays compile-only (B168,
no macOS in the lab).

## The integration tier: per language ecosystem, not per framework

Backends belong to the **language**, not the framework: every Python framework uses the same psycopg, so the
integration tier is ~10 ecosystems × 4 backends, not 38 paths × 4. Each ecosystem gets one shared integration
module (an `ItemStore` backed by Postgres, plus the cache, event and object adapters) that its frameworks reuse.

**Backends in scope (CI-reachable as hermetic sidecars, never the live lab stores):**

| Backend | Exercise | Why this one |
|---|---|---|
| **Postgres 16** | the `ItemStore` (create/get/list, a migration) | the estate's core store; every ecosystem has a mature client |
| **Valkey 8** | read-through cache for `GET /items/{id}` | the estate's cache (Feast online store, GlitchTip) |
| **Redpanda** (Kafka API) | publish an `item.created` event, read it back | the estate's event bus (DataHub, Flink) |
| **MinIO** (S3 API) | store an item attachment, read it back | the estate's object store (Iceberg, backups) |

**Out of scope, with the reason:** Trino, Neo4j and the Tier-2 stores (Cassandra, Mongo, Cockroach, MusicBrainz):
a service template rarely starts there, and their containers are heavy. Vector stores (Qdrant, Weaviate, pgvector):
Python-only in the estate; a later item if wanted. Keycloak/OIDC: a real Keycloak sidecar is heavy and a static
JWKS would be a mock; a later "auth tier" item. **Never mock a backend and count it as covered.**

| Ecosystem | Paths | Postgres | Valkey | Kafka API | S3 API |
|---|---|---|---|---|---|
| Python | 4 | psycopg 3 | redis-py | confluent-kafka | boto3 |
| Node | 3 | pg | ioredis | kafkajs | @aws-sdk/client-s3 |
| JVM (Java, Kotlin, Scala, Clojure) | 7 | JDBC (pgjdbc) / Doobie for http4s / next.jdbc | Lettuce | kafka-clients | AWS SDK v2 |
| Go | 4 | pgx | go-redis | franz-go | minio-go |
| Rust | 3 | sqlx | redis-rs | rdkafka | aws-sdk-s3 |
| .NET | 1 | Npgsql | StackExchange.Redis | Confluent.Kafka | AWSSDK.S3 |
| Ruby | 2 | pg / ActiveRecord | redis | rdkafka | aws-sdk-s3 |
| PHP | 1 | PDO pgsql | predis | skip (needs the rdkafka C extension in the image; revisit) | aws-sdk-php |
| BEAM (Elixir, Erlang) | 3 | Postgrex / epgsql | Redix / eredis | brod | ExAws / erlcloud |
| Long tail (Swift, Dart, Haskell, Julia, Perl, R, Lua, Ada, C, C++) | 10 | **Postgres only** where a maintained client exists (PostgresNIO, postgres.dart, postgresql-simple, LibPQ.jl, Mojo::Pg, RPostgres, pgmoon, GNATCOLL.SQL, libpq, libpqxx) | skip | skip | skip — the long tail proves its language can reach the core store; the rest is matrix cost without lab value |

**CI shape:** one `integration-<ecosystem>` step per ecosystem, with the four backends as Woodpecker `services:`
sidecars, selected by changed paths (the B161 selector) so a run pays only for what changed. **Unproven here:** no
workflow in this repo uses `services:` yet on the Kubernetes backend. The first sub-item proves it before any other
depends on it; if it cannot work, the fallback is the existing pattern (`test-integration-datahub` runs the backend
image itself), decided there, with evidence.

## The path set: 48, not 21

**Recommendation: all 48.** The 21 B153 paths were the set when B163 was filed; B160 and B164 have since made 48
first-class paths with the same lanes and smoke. Deepening only 21 leaves 27 scaffolds that inherit the stub, the
exact drift B163 exists to remove. The cost is bounded by the per-ecosystem integration tier (the long tail gets
Postgres only) and by sequencing. **Decided 2026-11-25: all 48** (owner: "Approve, all 48", approving this design and
the breakdown below).

## Sub-item breakdown (approved 2026-11-25; filed as B260-B270)

Sequenced reference-first, then per-ecosystem batches (the B153 cadence). Each is independently shippable, keeps
every path green, raises its lines in `tests/lang/coverage-baseline.tsv`, and tests the scaffold
(`new-service.sh` output), not only the template.

| # | Sub-item | Paths | Delivers |
|---|---|---|---|
| 1 | **Reference: Python/FastAPI + the harness** — B260 (EMA-363) | python/fastapi | deep contract v2 in FastAPI; the smoke Job's v2 assertions in `run-golden-path-jobs.sh` (shared by all paths after); the Python integration module; **proof of `services:` sidecars** (or the fallback); the scaffold test; CI cost measured |
| 2 | Python: the other three — B261 (EMA-364) | django, flask, litestar | v2 in each idiom; reuse the Python integration module |
| 3 | Node — B262 (EMA-365) | express, fastify, nestjs | v2 + Node integration module |
| 4 | JVM — B263 (EMA-366) | spring-boot, quarkus, micronaut, ktor, http4s, ring, compojure | v2 + JVM integration module (largest batch; may split Java / non-Java) |
| 5 | Go — B264 (EMA-367) | nethttp, gin, echo, fiber | v2 + Go integration module |
| 6 | Rust — B265 (EMA-368) | axum, actix, rocket | v2 + Rust integration module |
| 7 | .NET, Ruby, PHP — B266 (EMA-369) | aspnet, rails, sinatra, slim | v2 + three integration modules |
| 8 | BEAM — B267 (EMA-370) | phoenix, plug, cowboy | v2 + BEAM integration module |
| 9 | Long tail — B268 (EMA-371) | swift, dart, haskell, julia, perl, r, lua, ada, c, cpp | v2 + Postgres only |
| 10 | Frontends — B269 (EMA-372) | angular, astro, nextjs, react-router, vite-react, vue | adapted v2 (routing, forms, fetching, state, component tests) |
| 11 | Mobile — B270 (EMA-373) | flutter, react-native, swift-tokamak (swift-ios compile-only) | adapted v2 |

**Order rationale:** 1 sets the contract, harness and CI pattern everything else reuses; 2-8 follow the estate's
weight (Python first, the long tail last); the clients (10-11) come after the services they would call.

## Risks

| Risk | Mitigation |
|---|---|
| Matrix explosion | the deep contract is uniform; integration is per ecosystem; the long tail is Postgres-only |
| CI wall clock | change-selected integration steps; each sub-item measures and records its CI minutes; integration runs in the parallel fixtures workflows (B200) |
| `services:` not working on the k8s backend | proven (or replaced) in sub-item 1 before anything depends on it |
| Template drift | each sub-item scaffolds a service with `new-service.sh` and runs its lanes, not only the template's |
| A long-tail framework cannot meet a row | the catalog's skip column records it with the reason; never faked |
