# Golden path Elixir / Phoenix (API-only). Multi-stage: mix release (bundles ERTS) → slim runtime.
# buildkit → registry.weyland.lab/golden-elixir-phoenix.
FROM elixir:1.17 AS build
WORKDIR /app
ENV MIX_ENV=prod
RUN mix local.hex --force && mix local.rebar --force
COPY mix.exs ./
RUN mix deps.get --only prod
COPY config config
COPY lib lib
RUN mix deps.compile && mix compile && mix release

# The release bundles ERTS, so the runtime needs only the shared libs OTP links against.
# bookworm-slim matches the elixir:1.17 (bookworm) build base.
FROM debian:bookworm-slim
WORKDIR /app
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser \
 && apt-get update && apt-get install -y --no-install-recommends libncurses6 openssl ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*
# LAN-only $0 canary: PHX_SERVER makes the release serve; a fixed non-secret SECRET_KEY_BASE (>=64 bytes)
# so boot never demands a real one. A real service injects both at runtime and never bakes a secret.
ENV PHX_SERVER=true PORT=8080 \
    SECRET_KEY_BASE=golden-elixir-phoenix-lab-canary-not-a-secret-0000000000000000000
COPY --from=build /app/_build/prod/rel/golden_phoenix ./
COPY smoke.sh ./
USER 10001
EXPOSE 8080
CMD ["bin/golden_phoenix", "start"]
