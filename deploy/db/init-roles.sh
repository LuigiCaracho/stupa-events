#!/bin/sh
# Postgres first-start hook (docker-entrypoint-initdb.d): stage 1 of roles.sql, then the
# role passwords from the container environment. POSIX sh, the alpine image has no bash.
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f /db/roles.sql

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v app_pw="$EVENTS_APP_PASSWORD" \
  -v migrator_pw="$EVENTS_MIGRATOR_PASSWORD" \
  -v public_pw="$EVENTS_PUBLIC_PASSWORD" <<'SQL'
ALTER ROLE events_app PASSWORD :'app_pw';
ALTER ROLE events_migrator PASSWORD :'migrator_pw';
ALTER ROLE events_public PASSWORD :'public_pw';
SQL
