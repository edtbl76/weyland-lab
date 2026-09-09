# Golden path PHP / Slim. Multi-stage: composer deps → php-cli runtime. buildkit → registry.weyland.lab/golden-php-slim.
FROM composer:2.7 AS build
WORKDIR /app
COPY composer.json ./
RUN composer install --no-dev --no-interaction --no-progress --optimize-autoloader
FROM php:8.3-cli
WORKDIR /app
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser \
 && apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY --from=build /app/vendor ./vendor
COPY src ./src
COPY public ./public
COPY smoke.sh ./
USER 10001
EXPOSE 8080
CMD ["php", "-S", "0.0.0.0:8080", "-t", "public", "public/index.php"]
