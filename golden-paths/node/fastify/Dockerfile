# Golden path Node/Fastify. Multi-stage: prod deps → alpine runtime. buildkit → registry.weyland.lab/golden-node-fastify.
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund --loglevel=error

FROM node:24-alpine
WORKDIR /app
RUN adduser -D -u 10001 appuser
COPY --from=build /app/node_modules ./node_modules
COPY package.json ./
COPY src ./src
USER 10001
EXPOSE 8080
CMD ["node", "src/server.js"]
