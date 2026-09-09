# Golden path — C++ / cpp-httplib

A blessed paved-road C++ HTTP service on **cpp-httplib** (single-header, CMake-fetched — no vendored
sources, no asio build fight). **Runnable · ephemeral · extendable.** Conforms to the golden-path
contract ([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): `/health` `/ready`
`/metrics` `/hello`.

```
cmake -S . -B build && cmake --build build --target unit_tests
./build/unit_tests --test-suite-exclude=selfcheck    # 4 contract tests (doctest, over the payload builders)
./build/unit_tests --test-suite=selfcheck            # the deliberate failure (proves the lane propagates)
bash scripts/run-lang-tests.sh cpp                    # the CI lane runs this golden path as its fixture
```

Layout: `CMakeLists.txt` (FetchContent cpp-httplib + doctest; static libstdc++ so the runtime is a plain
debian-slim); `src/handlers.hpp` are pure payload-builders (unit-testable without an HTTP layer — C++
has no in-process request mock, so these cover the payload logic and the smoke curls the real server);
`src/main.cpp` wires them onto the httplib server on `$PORT` (8080). Metrics = a hand-rolled Prometheus
text endpoint. The deliberate test lives in the doctest `selfcheck` suite.

**Ephemeral Job + scaffolding + the onboarding declaration** work as the Python FastAPI reference — see
[../../python/fastapi/README.md](../../python/fastapi/README.md) and `scripts/run-golden-path-jobs.sh`
(reads `.smoke`). Scaffold a real service: `scripts/new-service.sh cpp/httplib <your-service>`.
