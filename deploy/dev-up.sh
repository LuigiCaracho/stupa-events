#!/usr/bin/env bash
# Start the local dev environment on the host: containers, migrations, API, worker and ng serve as user units.
# Reads backend/.env via systemd EnvironmentFile; NixOS needs libstdc++ and libmagic on LD_LIBRARY_PATH.
set -euo pipefail
R="$(cd "$(dirname "$0")/.." && pwd)"
LIBS="$(nix build --no-link --print-out-paths nixpkgs#stdenv.cc.cc.lib nixpkgs#file | grep -v -- -man | sed 's|$|/lib|' | paste -sd:)"
docker compose -f "$R/deploy/docker-compose.dev.yml" up -d
for _ in $(seq 1 30); do
  curl -fs -o /dev/null http://127.0.0.1:8090/realms/stupa-events/.well-known/openid-configuration && break
  sleep 5
done
run() { systemd-run --user --quiet --collect --unit="$1" --working-directory="$2" -p EnvironmentFile="$R/backend/.env" --setenv=LD_LIBRARY_PATH="$LIBS" "${@:3}"; }
systemd-run --user --quiet --wait --pipe --collect --working-directory="$R/backend" -p EnvironmentFile="$R/backend/.env" --setenv=LD_LIBRARY_PATH="$LIBS" "$R/backend/.venv/bin/alembic" upgrade head
for u in stupa-api stupa-worker stupa-ng; do systemctl --user stop "$u" 2>/dev/null || true; done
run stupa-api "$R/backend" "$R/backend/.venv/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8000
run stupa-worker "$R/backend" "$R/backend/.venv/bin/arq" worker.main.WorkerSettings
systemd-run --user --quiet --collect --unit=stupa-ng --working-directory="$R/frontend" "$R/frontend/node_modules/.bin/ng" serve --port 4200
for _ in $(seq 1 40); do curl -fs -o /dev/null http://localhost:4200/ && break; sleep 3; done
systemctl --user --no-pager --plain list-units 'stupa-*' | awk '{print $1, $3, $4}'
