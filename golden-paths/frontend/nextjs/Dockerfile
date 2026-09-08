# Golden path Frontend/Next.js. Multi-stage: next build (standalone) → alpine runtime (node server.js).
# buildkit → registry.weyland.lab/golden-frontend-nextjs.
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund --loglevel=error
COPY . .
RUN npm run build

FROM node:24-alpine
WORKDIR /app
RUN adduser -D -u 10001 appuser && apk add --no-cache curl
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY smoke.sh ./
USER 10001
EXPOSE 8080
ENV PORT=8080 HOSTNAME=0.0.0.0
CMD ["node", "server.js"]
