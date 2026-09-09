# Golden path Scala / http4s. Multi-stage: sbt stage (native-packager) → JRE. buildkit → registry.weyland.lab/golden-scala-http4s.
FROM sbtscala/scala-sbt:eclipse-temurin-21.0.12_8_1.13.0_3.8.4 AS build
WORKDIR /app
COPY . .
RUN sbt stage
FROM eclipse-temurin:21-jre
WORKDIR /app
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser \
 && apt-get update && apt-get install -y --no-install-recommends curl bash && rm -rf /var/lib/apt/lists/*
# native-packager `stage` output: bin/<launcher> (a bash script) + lib/*.jar.
COPY --from=build /app/target/universal/stage /app
COPY smoke.sh ./
USER 10001
EXPOSE 8080
ENTRYPOINT ["/app/bin/golden-scala-http4s"]
