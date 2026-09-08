# Golden path Rust / actix. Multi-stage: rust build → debian-slim run. buildkit → registry.weyland.lab/golden-rust-actix.
FROM rust:1-slim AS build
WORKDIR /app
COPY Cargo.toml Cargo.lock* ./
COPY src ./src
RUN cargo build --release
FROM debian:bookworm-slim
WORKDIR /app
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser \
    && apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=build /app/target/release/server ./
COPY smoke.sh ./

USER 10001
EXPOSE 8080
CMD ["./server"]
