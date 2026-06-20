# Multi-stage build for the weyland IDP — builds the whole app (install -> tsc -> bundle) INSIDE Docker
# from the committed source. The only host requirement is Docker + BuildKit; reproducible from the repo
# (yarn.lock + .yarn/releases pin everything). This replaces the create-app "host-build" variant at
# packages/backend/Dockerfile, which required pre-running yarn build:backend on a matching Node host.
#
#   DOCKER_BUILDKIT=1 docker image build . -t weyland-idp:local
#
# Context = this directory (services/weylandidp). Base image matches what create-app generated (node:24).

# ---------------------------------------------------------------- stage 1: install + build the bundle
FROM node:22-bookworm-slim AS build
ENV PYTHON=/usr/bin/python3
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends python3 g++ build-essential && \
    rm -rf /var/lib/apt/lists/*
USER node
WORKDIR /app

# Yarn config + manifests first so the (slow) install layer caches until deps actually change.
COPY --chown=node:node .yarn ./.yarn
COPY --chown=node:node .yarnrc.yml package.json yarn.lock backstage.json ./
COPY --chown=node:node packages packages
RUN --mount=type=cache,target=/home/node/.cache/yarn,sharing=locked,uid=1000,gid=1000 \
    yarn install --immutable

# Then the rest of the source, compile, and produce the backend bundle + skeleton.
COPY --chown=node:node . .
RUN yarn tsc
RUN yarn build:backend

# ---------------------------------------------------------------- stage 2: lean runtime (prod deps only)
FROM node:22-bookworm-slim
ENV PYTHON=/usr/bin/python3
ENV NODE_ENV=production
ENV NODE_OPTIONS="--no-node-snapshot"
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends python3 g++ build-essential libsqlite3-dev && \
    rm -rf /var/lib/apt/lists/*
USER node
WORKDIR /app

COPY --from=build --chown=node:node /app/.yarn ./.yarn
COPY --from=build --chown=node:node /app/.yarnrc.yml /app/package.json /app/yarn.lock /app/backstage.json ./
COPY --from=build --chown=node:node /app/packages/backend/dist/skeleton.tar.gz ./
RUN tar xzf skeleton.tar.gz && rm skeleton.tar.gz
RUN --mount=type=cache,target=/home/node/.cache/yarn,sharing=locked,uid=1000,gid=1000 \
    yarn workspaces focus --all --production && rm -rf "$(yarn cache clean)"

# examples are referenced by the base app-config; harmless to keep. The bundle is the built backend.
COPY --from=build --chown=node:node /app/examples ./examples
COPY --from=build --chown=node:node /app/packages/backend/dist/bundle.tar.gz /app/app-config.yaml /app/app-config.production.yaml ./
RUN tar xzf bundle.tar.gz && rm bundle.tar.gz

CMD ["node", "packages/backend", "--config", "app-config.yaml", "--config", "app-config.production.yaml"]
