#!/usr/bin/env bash
# Compose lint (PLAN 11.1, 11.7): the stack stays separate from the Workflow stack. Checks the
# rendered config and the scripts. Run from anywhere: deploy/compose-lint.sh
# Rules: project name stupa-events, no host port 8080/5433, FORWARDED_ALLOW_IPS never "*",
# web on the fixed IP, mem_limit on every service, every nginx location includes the CSP
# snippet, no prune in scripts.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
cp .env.dev.example "${tmp}/env"
export ENV_FILE="${tmp}/env"
compose=(docker compose -f docker-compose.yml -f docker-compose.keycloak.yml --env-file "${tmp}/env")

"${compose[@]}" config -q
docker compose -f docker-compose.dev.yml config -q
cfg="$("${compose[@]}" config --format json)"
failed=0
fail() { echo "compose-lint: $*" >&2; failed=1; }

[[ "$(jq -r .name <<<"${cfg}")" == stupa-events ]] || fail "project name must be stupa-events"

forbidden="$(jq -r '[.services[].ports[]? | select(.published == "8080" or .published == "5433") | .published] | join(",")' <<<"${cfg}")"
[[ -z "${forbidden}" ]] || fail "forbidden host port(s): ${forbidden}"

[[ "$(jq -r '.services.api.environment.FORWARDED_ALLOW_IPS' <<<"${cfg}")" != '*' ]] || fail "FORWARDED_ALLOW_IPS is *"
grep -Eq '^FORWARDED_ALLOW_IPS=\*' .env.example .env.dev.example && fail "FORWARDED_ALLOW_IPS=* in an env example"

[[ "$(jq -r '.services.web.networks.internal.ipv4_address' <<<"${cfg}")" == 172.29.10.10 ]] || fail "web needs 172.29.10.10"
[[ "$(jq -r '.networks.internal.ipam.config[0].subnet' <<<"${cfg}")" == 172.29.10.0/24 ]] || fail "subnet must be 172.29.10.0/24"

missing="$(jq -r '[.services | to_entries[] | select(.key != "keycloak" and (.value.mem_limit // null) == null) | .key] | join(",")' <<<"${cfg}")"
[[ -z "${missing}" ]] || fail "mem_limit missing on: ${missing}"

bare="$(awk '/^[[:space:]]*location /{loc=$0; seen=0; open=1; next}
  open && /security-headers\.conf/{seen=1}
  open && /^[[:space:]]*}/{if(!seen) print loc; open=0}' web/nginx.conf)"
[[ -z "${bare}" ]] || fail "nginx location without the CSP include: ${bare}"

if grep -nE 'docker (system|image|volume|container|builder) prune' *.sh ../.github/workflows/*.yml; then
  fail "prune in scripts or workflows"
fi

[[ "${failed}" == 0 ]] && echo "compose-lint ok"
exit "${failed}"
