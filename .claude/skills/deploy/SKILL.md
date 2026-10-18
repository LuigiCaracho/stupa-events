---
name: deploy
description: The STUPA Events compose stack, nginx with CSP, DB roles, backup and restore scripts, CI and the dev IdP. Use when working on deploy/, .github/, docker-compose files, nginx.conf, security-headers.conf, roles.sql, env files, the Keycloak realm or the Authentik blueprint.
---

<!-- Copied from STUPA-Workflow@93c33d6 .claude/skills/deploy/SKILL.md (adapted). -->
# Deploy stack: `deploy/`, `.github/`, `docs/authentik/`

**Does:** One VM, Docker Compose project `stupa-events`, plain HTTP inside, an external Caddy terminates TLS
(`events.reutlingen.university` to `127.0.0.1:8081`). It runs beside the Workflow stack (`antragsplattform`), so ports,
volumes and subnet are disjoint.

**Key files:**
- `docker-compose.yml`: `web` (nginx + SPA, `127.0.0.1:8081`, fixed IP `172.29.10.10`), `migrate` (one-shot
  `alembic upgrade head`), `api`, `worker`, `postgres` (`127.0.0.1:5434`), `redis`, `minio`, `clamav`. Net `internal`
  `172.29.10.0/24`, `FORWARDED_ALLOW_IPS=172.29.10.10`, `mem_limit`/`cpus` and healthchecks everywhere, images pinned.
- `docker-compose.keycloak.yml`: overlay with the dev IdP (Keycloak 8090, realm `deploy/keycloak/stupa-events-realm.json`),
  `extra_hosts host.docker.internal`. `docker-compose.dev.yml`: backing services only (postgres 5434, redis 6381, minio
  9100, clamav 3311, keycloak 8090) for host-run backend and frontend.
- `.env.example` (production, `CHANGE_ME` placeholders), `.env.dev.example` (throwaway dev values, copy to `.env.dev`).
  Names equal the backend `Settings` fields; compose-only variables are listed at the end.
- `web/nginx.conf`, `web/security-headers.conf` (CSP of PLAN 11.2, included in the server and in EVERY location because
  `add_header` in a location replaces the inherited set), `web/api-proxy.conf`. Paths `/api`, `/ics/`, `/e/`, `/k/`,
  `/suche`, `/sitemap.xml`, `/robots.txt`; upload limits 11m (poster) and 26m (documents), 1m elsewhere; `/ics/p/` is not
  logged with its path; `/api/public/` is logged without query.
- `db/roles.sql` + `db/init-roles.sh`: roles `events_migrator`, `events_app` (no DELETE, append-only tables INSERT and
  SELECT only), `events_audit_writer`, `events_public` (SELECT on `public_*_v` only, connection limit 8, statement
  timeout 2 s). Stage 1 at first start, stage 2 after every `alembic upgrade head`.
- `backup.sh` (pg_dump custom through age, `mc mirror` of `events-attachments`, manifest), `restore-smoke.sh`
  (throwaway Postgres, compares revision and row counts), `smoke.sh` (health and CSP in each location),
  `compose-lint.sh`, `deploy.sh vX.Y.Z` (documented, never run).
- `.github/workflows/ci.yml`, `upstream-drift.yml` (weekly, opens an issue only), `scripts/upstream-drift.sh`.

**Rules:** never port 8080 or 5433, never `FORWARDED_ALLOW_IPS=*`, `set_real_ip_from` only with the exact Caddy IP
(placeholder `192.0.2.1`), no Docker prune commands anywhere, secrets never in git (`gitleaks`). Production secrets are
fresh and differ from the Workflow stack's. Never touch the live systems.

**Traps:**
- `ENV_FILE` (in the env file) selects the `env_file` of api, worker and migrate: `.env` or `.env.dev`.
- Keycloak keeps the Secure cookie flag on `localhost` but not on `host.docker.internal`; use the latter as in the contract.
- Docker's default log driver may be journald; use `journalctl` or `--log-driver json-file` when `docker logs` is empty.
- MinIO credentials of the app equal `MINIO_ROOT_*` until service accounts exist.

**Siblings:** `be-auth` (IdP), `be-events` (buckets, public role), `frontend` (build).
