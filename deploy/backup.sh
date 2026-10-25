#!/usr/bin/env bash
# Backup of the STUPA Events stack (PLAN 11.4): pg_dump custom format piped through age, a
# `mc mirror` of the private attachment bucket (derivatives in events-public are regenerable and
# skipped), the verified map archives of the tiles_data volume (the pinned Protomaps build expires
# after about a week, so the copy is the only source) and a manifest with row counts. Runs on the host, from cron (03:15).
# Needs: docker compose, age, jq, a deploy/.env with BACKUP_AGE_RECIPIENT, MINIO_ROOT_*.
# Usage: deploy/backup.sh   (BACKUP_DIR defaults to /srv/stupa-events/backups)
# Another stack, e.g. the dev services: COMPOSE_FILE=docker-compose.dev.yml ENV_FILE=.env.dev
# (docker compose reads COMPOSE_FILE itself; mc joins the network namespace of the minio container).
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
ENV_FILE="${ENV_FILE:-.env}"
BACKUP_DIR="${BACKUP_DIR:-/srv/stupa-events/backups}"
MC_IMAGE="${MC_IMAGE:-pgsty/mc:RELEASE.2026-10-18T00-00-00Z}"
compose=(docker compose --env-file "${ENV_FILE}")

env_value() { sed -n "s/^$1=//p" "${ENV_FILE}" | head -n1; }

recipient="$(env_value BACKUP_AGE_RECIPIENT)"
retention="$(env_value BACKUP_RETENTION_COUNT)"
[[ -n "${recipient}" ]] || { echo "BACKUP_AGE_RECIPIENT missing in ${ENV_FILE}" >&2; exit 1; }

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out="${BACKUP_DIR}/${stamp}"
mkdir -p "${out}/minio"
umask 077

"${compose[@]}" exec -T postgres pg_dump -U postgres -d events --format=custom \
  | age -r "${recipient}" > "${out}/db.dump.age"

export MC_HOST_events="http://$(env_value MINIO_ROOT_USER):$(env_value MINIO_ROOT_PASSWORD)@localhost:9000"
minio_container="$("${compose[@]}" ps -q minio)"
[[ -n "${minio_container}" ]] || { echo "minio is not running" >&2; exit 1; }
mc() { docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e MC_HOST_events --network "container:${minio_container}" -v "${out}/minio:/out" "${MC_IMAGE}" "$@"; }
mc mb --ignore-existing events/events-attachments >/dev/null
mc mirror --overwrite events/events-attachments /out/events-attachments >/dev/null

tiles_volume="$("${compose[@]}" config --format json | jq -r .name)_tiles_data"
if docker volume inspect "${tiles_volume}" >/dev/null 2>&1; then
  mkdir -p "${out}/tiles"
  docker run --rm -v "${tiles_volume}:/t:ro" -v "${out}/tiles:/out" alpine:3 sh -c 'cp /t/*.pmtiles /out/ && chmod -R a+rX /out'
fi

rows="$("${compose[@]}" exec -T postgres psql -U postgres -d events -At -F, -c "
  SELECT table_name,
         (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM %I', table_name), false, true, '')))[1]::text
  FROM information_schema.tables
  WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY 1")"
revision="$("${compose[@]}" exec -T postgres psql -U postgres -d events -At -c 'SELECT version_num FROM alembic_version')"

jq -n --arg createdAt "${stamp}" --arg revision "${revision}" --arg rows "${rows}" \
  --argjson files "$(cd "${out}/minio" && find . -type f -printf '%P\n' | jq -R . | jq -s .)" \
  '{createdAt: $createdAt, alembicRevision: $revision,
    rows: ($rows | split("\n") | map(split(",") | {(.[0]): (.[1] | tonumber)}) | add),
    attachmentFiles: $files}' > "${out}/manifest.json"

mapfile -t old < <(find "${BACKUP_DIR}" -mindepth 1 -maxdepth 1 -type d -name '20*' | sort -r | tail -n +"$(( ${retention:-14} + 1 ))")
for dir in "${old[@]}"; do rm -r -- "${dir}"; done

echo "backup ${out}"
