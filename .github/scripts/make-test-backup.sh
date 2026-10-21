#!/usr/bin/env bash
# Builds a small encrypted test backup of the CI database for `deploy/restore-smoke.sh`
# (E26, M5 12.4): pg_dump through age with a throwaway key, a manifest with row counts, an
# empty attachment folder (no MinIO in CI). Prints two lines: the backup dir and the key file.
# Usage: PGHOST=localhost PGUSER=postgres PGPASSWORD=... make-test-backup.sh <work-dir>
set -euo pipefail

work="${1:?work directory}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out="${work}/backups/${stamp}"
mkdir -p "${out}/minio"
umask 077

age-keygen -o "${work}/test.key" 2> "${work}/recipient.txt"
recipient="$(grep -o 'age1[0-9a-z]*' "${work}/recipient.txt" | head -n1)"
pg_dump -d events --format=custom | age -r "${recipient}" > "${out}/db.dump.age"

rows="$(psql -d events -At -F, -c "
  SELECT table_name,
         (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM %I', table_name), false, true, '')))[1]::text
  FROM information_schema.tables
  WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY 1")"
revision="$(psql -d events -At -c 'SELECT version_num FROM alembic_version')"

jq -n --arg createdAt "${stamp}" --arg revision "${revision}" --arg rows "${rows}" \
  '{createdAt: $createdAt, alembicRevision: $revision,
    rows: ($rows | split("\n") | map(split(",") | {(.[0]): (.[1] | tonumber)}) | add),
    attachmentFiles: []}' > "${out}/manifest.json"

echo "${work}/backups"
echo "${work}/test.key"
