# ── Build stage ───────────────────────────────────────────────────────────────
FROM node:20-slim AS builder

RUN npm install -g pnpm

WORKDIR /app

# Copiar manifests del monorepo para que pnpm resuelva el workspace
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY packages/ ./packages/

# APP_PATH: subdirectorio de la app a construir, e.g. apps/adjuster
ARG APP_PATH
COPY ${APP_PATH}/ ./${APP_PATH}/

# Instalar dependencias del workspace completo (necesario para packages/ internos)
RUN pnpm install --frozen-lockfile

# Build args para variables de Vite (se hornean en el bundle en build time)
ARG VITE_API_BASE_URL
ARG VITE_NOTIFICATIONS_URL
ARG VITE_ENVIRONMENT=production

ENV VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_NOTIFICATIONS_URL=${VITE_NOTIFICATIONS_URL} \
    VITE_ENVIRONMENT=${VITE_ENVIRONMENT}

RUN pnpm --filter "@slate/$(basename ${APP_PATH})" build

# ── Runtime stage ─────────────────────────────────────────────────────────────
# nginx-unprivileged: corre como usuario no-root, escucha en 8080 por defecto
FROM nginxinc/nginx-unprivileged:stable-alpine AS runtime

# Remover config por defecto
RUN rm /etc/nginx/conf.d/default.conf

# El entrypoint de nginx-unprivileged ejecuta 20-envsubst-on-templates.sh
# automáticamente: procesa /etc/nginx/templates/*.template → /etc/nginx/conf.d/
# Esto resuelve el problema de permisos — la sustitución ocurre como root en el entrypoint.
COPY apps/nginx.conf.template /etc/nginx/templates/default.conf.template

# Copiar assets compilados desde el builder
ARG APP_PATH
COPY --from=builder /app/${APP_PATH}/dist /usr/share/nginx/html

# Build args para metadata
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
ARG ENVIRONMENT=production

ENV PORT=8080

EXPOSE 8080
