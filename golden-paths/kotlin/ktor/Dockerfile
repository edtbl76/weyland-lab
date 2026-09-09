# Golden path Kotlin / Ktor. Multi-stage: gradle shadowJar → JRE. buildkit → registry.weyland.lab/golden-kotlin-ktor.
FROM gradle:8.10-jdk21 AS build
WORKDIR /home/gradle/src
COPY --chown=gradle:gradle . .
RUN gradle shadowJar --no-daemon
FROM eclipse-temurin:21-jre
WORKDIR /app
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser \
 && apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY --from=build /home/gradle/src/build/libs/*-all.jar app.jar
COPY smoke.sh ./
USER 10001
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
