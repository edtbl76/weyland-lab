# Golden path Node/NestJS. Multi-stage: install+tsc build → prod deps runtime. buildkit → registry.weyland.lab/golden-node-nestjs.
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund --loglevel=error
COPY tsconfig.json tsconfig.build.json ./
COPY src ./src
RUN npm run build && npm prune --omit=dev

FROM node:24-alpine
WORKDIR /app
RUN adduser -D -u 10001 appuser && apk add --no-cache curl
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY package.json ./
COPY smoke.sh ./
USER 10001
EXPOSE 8080
CMD ["node", "dist/main.js"]
