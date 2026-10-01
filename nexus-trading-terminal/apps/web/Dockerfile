# NEXUS web app (Next.js standalone server).
# Build context: repository root (npm workspaces).
FROM node:22-alpine AS deps
WORKDIR /app
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
COPY packages/shared-types/package.json packages/shared-types/package.json
RUN npm ci --no-audit --no-fund

FROM node:22-alpine AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1 NEXT_STANDALONE=1
# The Next.js server proxies /api/* to this URL (server-side only).
ARG NEXUS_API_URL=http://api:8000
ENV NEXUS_API_URL=${NEXUS_API_URL}
COPY --from=deps /app/node_modules ./node_modules
COPY package.json package-lock.json ./
COPY packages/ packages/
COPY apps/web/ apps/web/
RUN npm run build -w @nexus/web

FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN adduser -D -u 10001 nexus
COPY --from=build --chown=nexus /app/apps/web/.next/standalone ./
COPY --from=build --chown=nexus /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=build --chown=nexus /app/apps/web/public ./apps/web/public
USER nexus
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD wget -qO- http://127.0.0.1:3000/ >/dev/null || exit 1
CMD ["node", "apps/web/server.js"]
