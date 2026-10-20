# Dashboard (API + gebaute UI) als ein Container. Build-Kontext ist das Repo-Root:
#   docker build -f deploy/dashboard/Dockerfile -t spec-agent-dashboard:latest .

# ---- Build ----
FROM node:22-bookworm-slim AS build
WORKDIR /repo
RUN corepack enable
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml tsconfig.base.json ./
COPY packages/contracts packages/contracts
COPY apps apps
RUN pnpm install --frozen-lockfile --filter @sak/dashboard-api... --filter @sak/dashboard-web...
RUN pnpm --filter @sak/dashboard-api --filter @sak/dashboard-web run build

# ---- Laufzeit ----
FROM node:22-bookworm-slim AS runtime
ENV NODE_ENV=production \
    PORT=3000 \
    SAK_DB_PATH=/data/dashboard.db
WORKDIR /app
# Nur das native Modul bleibt extern (vom Bundle ausgenommen). Version passt zum Lockfile.
ARG BETTER_SQLITE3_VERSION=13.0.3
# "type": "module" vorab setzen: das Bundle ist ESM, sonst warnt Node (MODULE_TYPELESS_PACKAGE_JSON).
RUN echo '{"name":"spec-agent-dashboard-runtime","private":true,"type":"module"}' > /app/package.json \
    && npm install --omit=dev --no-audit --no-fund --no-package-lock --prefix /app better-sqlite3@${BETTER_SQLITE3_VERSION} \
    && npm cache clean --force
COPY --from=build /repo/apps/dashboard-api/dist apps/dashboard-api/dist
COPY --from=build /repo/apps/dashboard-web/dist apps/dashboard-web/dist
RUN mkdir -p /data && chown -R node:node /data
USER node
VOLUME ["/data"]
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:'+(process.env.PORT||3000)+'/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "apps/dashboard-api/dist/server.js"]
