# Golden path — C / libmicrohttpd

A blessed paved-road C HTTP service on **GNU libmicrohttpd** (a system dep). **Runnable · ephemeral ·
extendable.** Conforms to the golden-path contract
([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): `/health` `/ready` `/metrics`
`/hello`.

```
cmake -S . -B build && cmake --build build --target unit_tests
./build/unit_tests               # 5 checks over the payload builders (exit 0)
./build/unit_tests --selfcheck    # the deliberate failure (proves the lane propagates)
bash scripts/run-lang-tests.sh c  # the CI lane runs this golden path as its fixture
```

Layout: `CMakeLists.txt` (pkg-config finds libmicrohttpd); `src/handlers.c` are pure payload-builders
(unit-testable without the HTTP layer — the smoke curls the real server); `src/main.c` runs the MHD
daemon on `$PORT` (8080), dispatching on the URL. Metrics = a hand-rolled Prometheus text endpoint. The
test harness uses a `CHECK` macro (not `assert()`, which a Release `-DNDEBUG` build would compile away);
its `--selfcheck` arg triggers the deliberate failure.

**Ephemeral Job + scaffolding + the onboarding declaration** work as the Python FastAPI reference — see
[../../python/fastapi/README.md](../../python/fastapi/README.md) and `scripts/run-golden-path-jobs.sh`
(reads `.smoke`). Scaffold a real service: `scripts/new-service.sh c/libmicrohttpd <your-service>`.
