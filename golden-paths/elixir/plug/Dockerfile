# Golden path Elixir / Plug. Multi-stage: mix release (self-contained, bundles ERTS) → slim runtime.
# buildkit → registry.weyland.lab/golden-elixir-plug.
FROM elixir:1.17 AS build
WORKDIR /app
ENV MIX_ENV=prod
RUN mix local.hex --force && mix local.rebar --force
COPY mix.exs ./
RUN mix deps.get --only prod
COPY lib lib
RUN mix deps.compile && mix release

# The release bundles ERTS, so the runtime needs only the shared libs OTP links against (openssl,
# ncurses, libstdc++ via debian-slim). bookworm-slim matches the elixir:1.17 (bookworm) build base.
FROM debian:bookworm-slim
WORKDIR /app
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser \
 && apt-get update && apt-get install -y --no-install-recommends libncurses6 openssl ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*
COPY --from=build /app/_build/prod/rel/golden_plug ./
COPY smoke.sh ./
USER 10001
EXPOSE 8080
CMD ["bin/golden_plug", "start"]
