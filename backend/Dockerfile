# Copied from STUPA-Workflow@93c33d6 backend/Dockerfile (no pg_dump client, events names)
# Backend image. The api, worker and migrate services share it; compose overrides the command.
# The build context is the repository root (docker-compose.yml: context: ..), because the stage
# `spa` builds the frontend: the API fills the built index.html with title, Open Graph and JSON-LD
# (B1 contract 2.8) and must name the same bundles as the nginx image. The ignore list for this
# build is backend/Dockerfile.dockerignore; the web image keeps the root .dockerignore.

FROM node:24-alpine AS spa
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# libmagic1: MIME sniffing for python-magic.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Dependencies in their own layer, before the source: a code change then invalidates only
# the fast install of the package. tomllib reads the list from pyproject.toml.
COPY backend/pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# The image also carries the alembic config and the migrations, so the migrate service
# can run `alembic upgrade head` on a fresh database.
COPY backend/app ./app
COPY backend/worker ./worker
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY backend/seeds ./seeds
RUN --mount=type=cache,target=/root/.cache/pip pip install --no-deps .

# The shell reads this file (SPA_INDEX_PATH); nothing else of the frontend is in the image.
COPY --from=spa /app/dist/*/browser/index.html /app/spa/index.html

# Do not run as root. The container needs read access to /app only.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# Keep forwarded-allow-ips narrow. Never set it to "*". Compose passes the proxy address.
# --no-access-log: uvicorn would write the request line with the query, and no search text belongs in a log.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log --proxy-headers --forwarded-allow-ips \"${FORWARDED_ALLOW_IPS:-127.0.0.1}\""]
