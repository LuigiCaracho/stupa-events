#!/usr/bin/env bash
# Copied from STUPA-Workflow@93c33d6 deploy/deploy.sh (adapted).
# Production update of the STUPA Events stack on the VM: check out an annotated release tag,
# update submodules, build under flock, recreate only the services whose image changed, then
# apply the stage-2 DB grants. Documented only, never run by the build tooling.
# Never prunes Docker resources: the host also runs the Workflow stack (compose lint enforces this).
# Usage: deploy/deploy.sh vMAJOR.MINOR.PATCH
set -euo pipefail

TAG="${1:?usage: deploy.sh vMAJOR.MINOR.PATCH}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}/deploy"

[[ "${TAG}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "tag must look like v1.2.3" >&2; exit 1; }
[[ -f .env ]] || { echo "deploy/.env missing: cp .env.example .env and fill it" >&2; exit 1; }
if grep -q 'CHANGE_ME' .env; then
  echo "deploy/.env still holds CHANGE_ME placeholders" >&2
  exit 1
fi

if ! grep -Eq '^TRUSTED_PROXY_IP=[0-9a-f.:]+$' .env || grep -q '^TRUSTED_PROXY_IP=192\.0\.2\.1$' .env; then
  echo "deploy/.env needs TRUSTED_PROXY_IP set to the real TLS proxy address (not 192.0.2.1)" >&2
  exit 1
fi

git -C "${ROOT}" fetch --tags --force
[[ "$(git -C "${ROOT}" cat-file -t "refs/tags/${TAG}")" == tag ]] || { echo "${TAG} is not an annotated tag" >&2; exit 1; }
git -C "${ROOT}" checkout --detach "refs/tags/${TAG}"
git -C "${ROOT}" submodule sync --recursive
git -C "${ROOT}" submodule update --init --recursive

docker compose config -q
cfg="$(docker compose config --format json)"
project="$(jq -r .name <<<"${cfg}")"
read -r -a build_svcs <<<"$(jq -r '[.services | to_entries[] | select(.value.build) | .key] | join(" ")' <<<"${cfg}")"

image_id() { docker image inspect -f '{{.Id}}' "${project}-$1" 2>/dev/null || echo none; }

declare -A before
for svc in "${build_svcs[@]}"; do before["${svc}"]="$(image_id "${svc}")"; done

exec 9>/var/lock/stupa-events-build.lock
flock 9
docker compose build
flock -u 9

changed=()
for svc in "${build_svcs[@]}"; do
  if [[ "${before[${svc}]}" != "$(image_id "${svc}")" ]]; then changed+=("${svc}"); fi
done

if [[ "${#changed[@]}" -gt 0 ]]; then
  docker compose up -d --no-build "${changed[@]}"
else
  docker compose up -d --no-build
fi

docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d events -f /db/roles.sql >/dev/null

for _ in $(seq 1 60); do
  [[ "$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -q web)")" == healthy ]] && break
  sleep 5
done
./smoke.sh
echo "deployed ${TAG}: ${changed[*]:-no image change}"
