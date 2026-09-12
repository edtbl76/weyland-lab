# Golden path Haskell / Scotty. Multi-stage: haskell:9.8 build (cabal) -> debian:bullseye-slim run.
# buildkit -> registry.weyland.lab/golden-haskell-scotty.
#
# NOTE: GHC builds are SLOW — the Scotty dependency graph (warp/wai/aeson/...) compiles from
# source on the first build (10-30 min cold). Dependencies are built in their own cached layer
# (COPY the .cabal/project first, then `cabal build --only-dependencies`) so source edits reuse it.
# bullseye-slim MATCHES haskell:9.8's own base (Debian 11), so the dynamically-linked binary's
# glibc + libffi7 line up; a newer slim (bookworm libffi8) would break it at runtime.
FROM haskell:9.8 AS build
WORKDIR /app
# One COPY: the executable depends on the in-package library, so --only-dependencies can't
# pre-build deps without the sources anyway. cabal.project.freeze pins every version; the whole
# Scotty graph compiles in a couple of minutes. Copy the produced binary to a stable path.
# (.dockerignore keeps dist-newstyle out of the context.)
COPY . .
RUN cabal update \
  && cabal build exe:golden-haskell-scotty \
  && cp "$(cabal list-bin exe:golden-haskell-scotty)" /app/server

# Minimal non-root runtime. NOTE: haskell:9.8's base (Debian 11 bullseye) is EOL — its apt repos
# 404 (packages moved to archive.debian.org). So the runtime is the SUPPORTED bookworm-slim:
# glibc is backward-compatible, so the bullseye-built binary runs on bookworm's newer glibc, and
# curl/ca-certificates install from a live repo. The one library that differs is libffi: the GHC
# RTS links libffi.so.7 (bullseye) but bookworm ships libffi8 — so carry libffi.so.7 over from the
# build stage. libgmp.so.10 exists on both, installed from bookworm.
FROM debian:bookworm-slim
WORKDIR /app
RUN apt-get update \
  && apt-get install -y --no-install-recommends libgmp10 ca-certificates curl \
  && rm -rf /var/lib/apt/lists/* \
  && useradd -u 10001 -m appuser
COPY --from=build /usr/lib/x86_64-linux-gnu/libffi.so.7* /usr/lib/x86_64-linux-gnu/
COPY --from=build /app/server /app/server
COPY smoke.sh /app/smoke.sh
USER 10001
EXPOSE 8080
CMD ["/app/server"]
