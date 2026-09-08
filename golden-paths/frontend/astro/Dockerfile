# Golden path Frontend/Astro. Multi-stage: astro build (SSR) → alpine runtime. buildkit → registry.weyland.lab/golden-frontend-astro.
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
COPY smoke.sh ./
USER 10001
EXPOSE 8080
ENV HOST=0.0.0.0 PORT=8080
CMD ["node", "./dist/server/entry.mjs"]
