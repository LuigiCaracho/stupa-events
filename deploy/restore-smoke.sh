#!/usr/bin/env bash
# Restore smoke test (PLAN 11.4, 16.1 M1): decrypts the newest backup into a throwaway
# postgres container, restores it and compares revision and row counts with manifest.json.
# Never touches the running stack. Needs age, jq, docker and the age identity file.
# Usage: AGE_IDENTITY=deploy/secrets/backup-age.key deploy/restore-smoke.sh [backup-dir]
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
BACKUP_DIR="${BACKUP_DIR:-/srv/stupa-events/backups}"
AGE_IDENTITY="${AGE_IDENTITY:-secrets/backup-age.key}"
backup="${1:-$(find "${BACKUP_DIR}" -mindepth 1 -maxdepth 1 -type d -name '20*' | sort | tail -n 1)}"
name="ev-restore-smoke-$$"

[[ -f "${backup}/db.dump.age" && -f "${backup}/manifest.json" ]] || { echo "no backup in ${backup:-?}" >&2; exit 1; }
trap 'docker rm -f "${name}" >/dev/null 2>&1 || true' EXIT

docker run -d --name "${name}" -e POSTGRES_DB=events -e POSTGRES_PASSWORD=restore-smoke \
  -v "$PWD/db/roles.sql:/db/roles.sql:ro" postgres:16-alpine >/dev/null
until docker exec "${name}" pg_isready -U postgres -d events >/dev/null 2>&1; do sleep 1; done
sleep 2

psql_in() { docker exec -i "${name}" psql -v ON_ERROR_STOP=1 -U postgres -d events "$@"; }
psql_in -f /db/roles.sql >/dev/null
age -d -i "${AGE_IDENTITY}" "${backup}/db.dump.age" \
  | docker exec -i "${name}" pg_restore -U postgres -d events --exit-on-error
psql_in -f /db/roles.sql >/dev/null

revision="$(psql_in -At -c 'SELECT version_num FROM alembic_version')"
expected_revision="$(jq -r .alembicRevision "${backup}/manifest.json")"
[[ "${revision}" == "${expected_revision}" ]] || { echo "revision ${revision} != ${expected_revision}" >&2; exit 1; }

status=0
while IFS=$'\t' read -r table expected; do
  actual="$(psql_in -At -c "SELECT count(*) FROM \"${table}\"")"
  [[ "${actual}" == "${expected}" ]] || { echo "${table}: ${actual} != ${expected}" >&2; status=1; }
done < <(jq -r '.rows | to_entries[] | [.key, .value] | @tsv' "${backup}/manifest.json")

files="$(find "${backup}/minio" -type f | wc -l)"
[[ "${files}" == "$(jq '.attachmentFiles | length' "${backup}/manifest.json")" ]] || { echo "attachment file count differs" >&2; status=1; }

[[ "${status}" == 0 ]] && echo "restore smoke ok (${backup})"
exit "${status}"
