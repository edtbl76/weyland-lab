# Golden path C++ / cpp-httplib. Multi-stage: cmake build (fetches cpp-httplib) → slim runtime.
# buildkit → registry.weyland.lab/golden-cpp-httplib.
FROM gcc:14 AS build
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends cmake git && rm -rf /var/lib/apt/lists/*
COPY CMakeLists.txt ./
COPY src src
COPY test test
RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --target golden-cpp-httplib

# The server links libstdc++/libgcc statically (see CMakeLists), so the runtime needs only libc +
# pthread (both in glibc) + curl for the smoke. trixie-slim matches gcc:14's base (GLIBC 2.41): a
# bookworm-slim runtime (GLIBC 2.36) is too old — the binary pulls a GLIBC_2.38 symbol and won't start.
FROM debian:trixie-slim
WORKDIR /app
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser \
 && apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY --from=build /app/build/golden-cpp-httplib ./app
COPY smoke.sh ./
USER 10001
EXPOSE 8080
CMD ["./app"]
