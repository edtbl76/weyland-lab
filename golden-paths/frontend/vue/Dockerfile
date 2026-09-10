# Golden path Frontend/Vue3+Vite. Multi-stage: vite build → alpine runtime serving dist/ via server.mjs.
# buildkit → registry.weyland.lab/golden-frontend-vue.
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund --loglevel=error
COPY . .
RUN npm run build

FROM node:24-alpine
WORKDIR /app
RUN adduser -D -u 10001 appuser && apk add --no-cache curl
COPY package.json package-lock.json* ./
RUN npm install --omit=dev --no-audit --no-fund --loglevel=error
COPY --from=build /app/dist ./dist
COPY server.mjs smoke.sh ./
USER 10001
EXPOSE 8080
CMD ["node", "server.mjs"]
