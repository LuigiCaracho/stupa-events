# web: multi-stage. Builds the Angular SPA, then lets nginx serve it as static files.
# Copied from STUPA-Workflow@93c33d6 deploy/web/Dockerfile (adapted). The context is the repository root
# (docker-compose.yml: context: ..), so frontend/ and deploy/web/ are in reach. The ui-kit
# submodule must be checked out before the build.

FROM node:24-alpine AS build
WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine

COPY deploy/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY deploy/web/security-headers.conf deploy/web/api-proxy.conf deploy/web/proxy-cache.conf /etc/nginx/snippets/
COPY deploy/web/real-ip.conf.template /etc/nginx/templates/
COPY --from=build /app/dist/*/browser/ /usr/share/nginx/html/
