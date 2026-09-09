# Golden path Ruby / Rails (API-only). Multi-stage: bundle install → slim runtime.
# buildkit → registry.weyland.lab/golden-ruby-rails.
FROM ruby:3.3-slim AS build
WORKDIR /app
# build-essential compiles native gem extensions (puma has a C extension).
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY Gemfile ./
# `without development test` keeps rubocop and the test-only gems out of the runtime bundle; the setting
# is written to /app/.bundle/config and carried into the runtime stage so `bundle exec` honours it there.
RUN bundle config set --local without "development test" && bundle install --jobs 4

FROM ruby:3.3-slim
WORKDIR /app
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser \
 && apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY --from=build /usr/local/bundle /usr/local/bundle
COPY --from=build /app/.bundle /app/.bundle
COPY --from=build /app/Gemfile.lock ./
COPY Gemfile ./
COPY config ./config
COPY app ./app
COPY config.ru ./
COPY smoke.sh ./
USER 10001
EXPOSE 8080
CMD ["bundle", "exec", "puma", "-b", "tcp://0.0.0.0:8080"]
