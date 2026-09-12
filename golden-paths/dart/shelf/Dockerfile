# Golden path Dart / shelf. Multi-stage: dart:stable build (dart compile exe) -> debian:trixie-slim run.
# buildkit -> registry.weyland.lab/golden-dart-shelf.
# trixie-slim matches dart:stable's own base (Debian 13), so the AOT exe's glibc lines up.
FROM dart:stable AS build
WORKDIR /app
COPY pubspec.yaml pubspec.lock ./
RUN dart pub get
COPY . .
RUN dart pub get --offline
RUN dart compile exe bin/server.dart -o /app/server

# Minimal non-root runtime: the self-contained AOT exe + curl/sh for the .smoke harness.
FROM debian:trixie-slim
WORKDIR /app
RUN apt-get update \
  && apt-get install -y --no-install-recommends curl ca-certificates \
  && rm -rf /var/lib/apt/lists/* \
  && useradd -u 10001 -m appuser
COPY --from=build /app/server /app/server
COPY smoke.sh /app/smoke.sh
USER 10001
EXPOSE 8080
CMD ["/app/server"]
