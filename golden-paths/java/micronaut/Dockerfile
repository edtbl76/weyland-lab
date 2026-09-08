# Golden path Java / Micronaut. Multi-stage: maven build → JRE run. buildkit → registry.weyland.lab/golden-java-micronaut.
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /app
COPY pom.xml .
RUN mvn -B -q dependency:go-offline 2>/dev/null || true
COPY src ./src
RUN mvn -B -q -DskipTests package && cp target/golden-java-micronaut-*.jar app.jar
FROM eclipse-temurin:21-jre
WORKDIR /app
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser && apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY --from=build /app/app.jar /app/smoke.sh ./
USER 10001
EXPOSE 8080
CMD ["java", "-jar", "app.jar"]
