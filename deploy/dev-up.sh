#!/usr/bin/env bash
# Start the local dev environment on the host: containers, migrations, API, worker and ng serve as user units.
# Also seeds Listmonk (SMTP to Mailpit, API user, lists) and writes its token to backend/.env when missing.
# Reads backend/.env via systemd EnvironmentFile, then the optional gitignored overlay backend/dev.env.local
# (it wins; the Listmonk seed writes its token there when it exists); API and worker restart on failure, so the worker
# survives the Redis outage of the acceptance cache check; NixOS needs libstdc++ and libmagic on LD_LIBRARY_PATH.
set -euo pipefail
R="$(cd "$(dirname "$0")/.." && pwd)"
LIBS="$(nix build --no-link --print-out-paths nixpkgs#stdenv.cc.cc.lib nixpkgs#file | grep -v -- -man | sed 's|$|/lib|' | paste -sd:)"
docker compose -f "$R/deploy/docker-compose.dev.yml" up -d
for _ in $(seq 1 30); do
  curl -fs -o /dev/null http://127.0.0.1:8090/realms/stupa-events/.well-known/openid-configuration && break
  sleep 5
done
for _ in $(seq 1 30); do
  curl -fs -o /dev/null http://127.0.0.1:9002/health && break
  sleep 2
done
ENV_LOCAL="$R/backend/dev.env.local"
ENVF=(-p EnvironmentFile="$R/backend/.env" -p EnvironmentFile=-"$ENV_LOCAL")
compose() { docker compose -f "$R/deploy/docker-compose.dev.yml" "$@"; }
until compose exec -T postgres pg_isready -U postgres -d events >/dev/null 2>&1; do sleep 1; done
compose exec -T postgres sh /docker-entrypoint-initdb.d/10-roles.sh >/dev/null
if [[ -f "$ENV_LOCAL" ]]; then ENV_FILE="$ENV_LOCAL" "$R/deploy/listmonk-seed.sh"; else "$R/deploy/listmonk-seed.sh"; fi
run() { systemd-run --user --quiet --collect --unit="$1" --working-directory="$2" "${ENVF[@]}" --setenv=LD_LIBRARY_PATH="$LIBS" -p Restart=on-failure -p RestartSec=5 "${@:3}"; }
systemd-run --user --quiet --wait --pipe --collect --working-directory="$R/backend" "${ENVF[@]}" --setenv=LD_LIBRARY_PATH="$LIBS" "$R/backend/.venv/bin/alembic" upgrade head
compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d events -f /db/roles.sql >/dev/null
systemd-run --user --quiet --wait --pipe --collect --working-directory="$R/backend" "${ENVF[@]}" --setenv=LD_LIBRARY_PATH="$LIBS" "$R/backend/.venv/bin/python" -m scripts.listmonk_lists ||
  echo "dev-up: Listmonk lists not synced (backend/.env needs the SUBS_*, PGCRYPTO_EMAIL_KEY and LISTMONK_* keys of .env.host.example)" >&2
for u in stupa-api stupa-worker stupa-ng; do systemctl --user stop "$u" 2>/dev/null || true; done
run stupa-api "$R/backend" "$R/backend/.venv/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8000 --no-access-log
run stupa-worker "$R/backend" "$R/backend/.venv/bin/arq" worker.main.WorkerSettings
systemd-run --user --quiet --collect --unit=stupa-ng --working-directory="$R/frontend" "$R/frontend/node_modules/.bin/ng" serve --port 4200
for _ in $(seq 1 40); do curl -fs -o /dev/null http://localhost:4200/ && break; sleep 3; done
systemctl --user --no-pager --plain list-units 'stupa-*' | awk '{print $1, $3, $4}'
