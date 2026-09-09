# Golden path Clojure / Ring. Multi-stage: lein uberjar → JRE runtime.
# buildkit → registry.weyland.lab/golden-clojure-ring.
FROM clojure:temurin-21-lein AS build
WORKDIR /app
COPY project.clj ./
RUN lein deps
COPY src src
RUN lein uberjar

FROM eclipse-temurin:21-jre
WORKDIR /app
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser \
 && apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY --from=build /app/target/golden-ring-standalone.jar app.jar
COPY smoke.sh ./
USER 10001
EXPOSE 8080
CMD ["java", "-jar", "app.jar"]
