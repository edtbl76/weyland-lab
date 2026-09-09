# Golden path C / libmicrohttpd. Multi-stage: cmake build → slim runtime with the MHD runtime lib.
# buildkit → registry.weyland.lab/golden-c-libmicrohttpd.
FROM gcc:14 AS build
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends cmake pkg-config libmicrohttpd-dev \
 && rm -rf /var/lib/apt/lists/*
COPY CMakeLists.txt ./
COPY src src
COPY test test
RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --target golden-c-libmicrohttpd

# trixie-slim matches the gcc:14 build base (GLIBC 2.41) — a bookworm-slim runtime happens to run this
# binary today but is a glibc-skew trap the moment the code or libmicrohttpd pulls a newer symbol.
FROM debian:trixie-slim
WORKDIR /app
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser \
 && apt-get update && apt-get install -y --no-install-recommends libmicrohttpd12 curl \
 && rm -rf /var/lib/apt/lists/*
COPY --from=build /app/build/golden-c-libmicrohttpd ./app
COPY smoke.sh ./
USER 10001
EXPOSE 8080
CMD ["./app"]
