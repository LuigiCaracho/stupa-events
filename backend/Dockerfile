# Copied from STUPA-Workflow@93c33d6 backend/Dockerfile (no pg_dump client, events names)
# Backend image. The api, worker and migrate services share it; compose overrides the command.
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
COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# The image also carries the alembic config and the migrations, so the migrate service
# can run `alembic upgrade head` on a fresh database.
COPY app ./app
COPY worker ./worker
COPY alembic.ini ./
COPY migrations ./migrations
RUN --mount=type=cache,target=/root/.cache/pip pip install --no-deps .

# Do not run as root. The container needs read access to /app only.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

# Keep forwarded-allow-ips narrow. Never set it to "*". Compose passes the proxy address.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips \"${FORWARDED_ALLOW_IPS:-127.0.0.1}\""]
