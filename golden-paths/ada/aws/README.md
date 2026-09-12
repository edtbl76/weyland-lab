# Golden path — Ada / AWS (Ada Web Server)

A blessed paved-road **Ada** HTTP service on **AWS (the Ada Web Server)**, built with **Alire**
(`alr`). **Runnable · ephemeral · extendable.** Conforms to the golden-path contract
([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): `GET /health` · `/ready` ·
`/metrics` · `/hello`. Binds `0.0.0.0:8080` (AWS's default host `""` is all interfaces).

## Run it (locally)

```
alr build                 # resolves aws + aunit, builds bin/server and bin/test_runner
./bin/server              # then: curl localhost:8080/hello -> {"service":"golden-ada-aws","message":"hello, weyland"}
```

## Test it (the CI lane runs exactly this)

```
alr build                            # builds the test_runner
./bin/test_runner                    # 4 contract tests pass (exit 0)
./bin/test_runner --selfcheck        # the deliberate failure — runs + exits non-zero (proves the lane propagates)
```

The tests assert the **pure payload builders** in `src/golden_handlers.adb` (the same C/C++ pattern —
binding AWS in-process for a unit test is heavy, so AUnit tests the payloads and the `.smoke` curl
proves the real AWS server end-to-end). The `--selfcheck` flag flips `Test_Config.Selfcheck` **before**
the suite is built, which is the only thing that registers the deliberately-failing `Selfcheck_Tests`
into the run. **Fail-closed:** if that guard in `test/golden_suite.adb` were removed, `--selfcheck`
would run only the passing contract tests and exit 0 — the same fail-open trap the C and Elixir golden
paths guard against — so the guard is what makes the self-check meaningful. The exit status comes from
`AUnit.Run.Test_Runner_With_Status` (a real status, not just a printed report), so a CI gate reads `$?`
directly.

**Scan lane:** the free-toolchain Ada scanner is `gnatcheck` (LKQL/`libadalang-tools`); where it is not
installed the lane falls back to the compiler's own `-gnatwa -gnaty` warning + style enforcement (the
`.gpr` already sets `-gnatwa`). There is **no SPARK/`gnatprove`** step — this is plain Ada, not SPARK.

## Ephemeral Job (spin up in-cluster to exercise, then tear down)

Works as the Python FastAPI reference — see [../../python/fastapi/README.md](../../python/fastapi/README.md)
and `scripts/run-golden-path-jobs.sh` (reads `.smoke`). buildkit builds
`registry.weyland.lab/golden-ada-aws`, the run-to-completion Job starts it, asserts `/ready` +
`/hello`'s known payload via `smoke.sh`, exits 0, and is deleted. Never a Deployment.

## Scaffold a REAL service FROM this

```
scripts/new-service.sh ada/aws <your-service>
```

Rewrites `Service_Name` (in `src/golden_handlers.ads`), drops the selfcheck, and gives you a runnable,
gate-passing starting point. The declaration below is what makes the scaffolded service pass the
onboarding gates (B154/B155) **by construction** — fill each `<...>` and the guards go green:

```yaml
# --- applications.yaml (append under `applications:`) — check-onboarding-completeness.sh ---
- {key: <your-service>, deployed: true, metrics: true, ingress: <true|false>, name: <Your Service>,
   group: <ai-serving|data-platform|serving|...>, datahub_application: false, owns: [],
   capabilities: [], likec4: <yourServiceCamelId>, port_component: <your-service>,
   description: "<one line>"}

# --- apis.yaml (append under `apis:`) — check-api-lifecycle.sh ---
# AWS serves no native OpenAPI, so author the spec file by hand (there is no /openapi.json
# spec_source to capture). Point `spec` at the committed doc and omit spec_source.
- {id: <your-service>, owner: <your-service>, kind: openapi, status: published, version: "1.0",
   base: "http://<your-service>.weyland.svc:8080",
   spec: docs/api/specs/<your-service>.openapi.json, consumers: []}
```

```
# --- weyland.likec4 (add to the right zone) ---
yourServiceCamelId = component "Your Service" "<one line>"
```

After scaffolding: author `docs/api/specs/<svc>.openapi.json`, run `scripts/gen-api-contract-lock.sh`,
and the onboarding + API-lifecycle guards pass.

## Contract compliance

| Facet | This golden path |
|---|---|
| HTTP surface | `/health` `/ready` `/metrics` `/hello` (`src/server.adb` router over `src/golden_handlers.adb`) |
| Self-test | `test/handlers_tests.adb` (4 AUnit cases over the payload builders) + `test/selfcheck_tests.adb` (deliberate fail, gated by `--selfcheck` via `test/golden_suite.adb`) |
| Build | multi-stage non-root `Dockerfile` (Alire `gnat_native=14.2.1` + `gprbuild=26.x` build → `ubuntu:24.04` runtime) → `registry.weyland.lab/golden-ada-aws` |
| Observability | structured JSON logging on startup + `/metrics` (Prometheus text exposition, hello counter) |
| Toolchain | Alire (`alr`) 2.1.x; root marker `alire.toml` (+ `golden_ada_aws.gpr`); test runner `bin/test_runner` |

## Toolchain notes / gotchas

- **The Alire toolchain pin is load-bearing.** AWS 25.x pulls `gnatcoll`/`libgpr` 25.x, which do **not**
  compile under the FSF GNAT 13.3 that Ubuntu ships (a `GPR.Util … Timeval` skew). The combination that
  builds cleanly is Alire's **binary** `gnat_native=14.2.1` + `gprbuild=26.x`
  (`alr --force toolchain --select gnat_native=14.2.1 gprbuild=26.0.1`), which the Dockerfile pins.
- **A `rm apt-lists` build stage denies Alire its own apt fallback**, so the build stage pre-installs
  everything AWS's build shells out to: `build-essential` (the toolchain gcc compiles+links AWS's C
  helper `xoscons` / `aws-os_lib-tmplt.c` — needs C headers + `crt*.o` + `make`), `libssl-dev` (AWS
  declares `openssl` as a system dep and links `-lssl -lcrypto`), and `git`/`curl` (Alire clones its
  crate index over git and downloads the toolchain over curl).
- **Runtime shared libs — the fiddly part.** The AWS binary is **not** self-contained. It dynamically
  needs `libssl.so.3` + `libcrypto.so.3` (OpenSSL 3, dragged in by `curl` in the runtime) **and**
  `libgnat-14.so` + `libgnarl-14.so` — the GNAT runtime, which lives inside the Alire toolchain, not in
  any apt package. The Dockerfile copies those two `.so` out of the build stage into `/usr/local/lib`
  and `ldconfig`s them. The runtime base is `ubuntu:24.04` to match the build base's glibc 2.39 and
  OpenSSL 3.0 (the glibc/openssl-skew trap the C golden path documents).
- **`alire.toml` must be pure ASCII** — Alire's TOML parser rejects a UTF-8 em dash with
  `invalid UTF-8 encoding`. Use `-`, not `—`, even in comments.
