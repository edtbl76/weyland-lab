# Golden path Erlang / Cowboy. Multi-stage: rebar3 release (self-contained, bundles ERTS) → slim runtime.
# buildkit → registry.weyland.lab/golden-erlang-cowboy.
FROM erlang:27 AS build
WORKDIR /app
COPY rebar.config ./
RUN rebar3 deps
COPY . .
# relx `mode, prod` (rebar.config) bundles ERTS into the release regardless of rebar3 profile.
RUN rebar3 release

# The release bundles ERTS, so the runtime needs only the shared libs OTP links against (openssl,
# ncurses, libstdc++ via debian-slim). bookworm-slim matches the erlang:27 (bookworm) build base;
# an alpine/musl runtime would break the glibc-linked bundled ERTS.
FROM debian:bookworm-slim
WORKDIR /app
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser \
 && apt-get update && apt-get install -y --no-install-recommends libncurses6 openssl ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*
COPY --from=build /app/_build/default/rel/golden_cowboy ./
COPY smoke.sh ./
USER 10001
EXPOSE 8080
CMD ["bin/golden_cowboy", "foreground"]
