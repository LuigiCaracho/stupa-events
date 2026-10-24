#!/usr/bin/env bash
# Compose lint (PLAN 11.1, 11.7): the stack stays separate from the Workflow stack. Checks the
# rendered config and the scripts. Run from anywhere: deploy/compose-lint.sh
# Rules: project name stupa-events, no host port 8080/5433, FORWARDED_ALLOW_IPS never "*",
# web on the fixed IP, mem_limit on every service, every nginx location includes the CSP
# snippet, no prune in scripts. B1: the proxy cache snippet sends no cookie and never serves
# /ics/p/, the server access log has no query string (only /ics/p/ is redacted differently),
# port 80 of the stack is published once.
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
grep -Eq '^TRUSTED_PROXY_IP=192\.0\.2\.1' .env.example && fail ".env.example must not ship the TRUSTED_PROXY_IP placeholder"
grep -q 'set_real_ip_from 192.0.2.1' web/nginx.conf web/real-ip.conf.template && fail "set_real_ip_from placeholder hard-coded in nginx"
grep -Eq '^TRUSTED_PROXY_IP=[0-9.]+$' .env.dev.example || fail ".env.dev.example needs TRUSTED_PROXY_IP"

[[ "$(jq -r '.networks.internal.ipam.config[0].subnet' <<<"${cfg}")" == 172.29.10.0/24 ]] || fail "subnet must be 172.29.10.0/24"

missing="$(jq -r '[.services | to_entries[] | select(.key != "keycloak" and (.value.mem_limit // null) == null) | .key] | join(",")' <<<"${cfg}")"
[[ -z "${missing}" ]] || fail "mem_limit missing on: ${missing}"

bare="$(awk '/^[[:space:]]*location /{loc=$0; seen=0; open=1; next}
  open && /security-headers\.conf/{seen=1}
  open && /^[[:space:]]*}/{if(!seen) print loc; open=0}' web/nginx.conf)"
[[ -z "${bare}" ]] || fail "nginx location without the CSP include: ${bare}"

grep -Eq '^proxy_set_header Cookie ""' web/proxy-cache.conf || fail "proxy-cache.conf must reset the Cookie header"
grep -Eq '^proxy_ignore_headers Set-Cookie' web/proxy-cache.conf || fail "proxy-cache.conf must ignore Set-Cookie"
direct="$(grep -nE '^[[:space:]]*proxy_cache[[:space:]]' web/nginx.conf || true)"
[[ -z "${direct}" ]] || fail "proxy_cache set in nginx.conf outside snippets/proxy-cache.conf: ${direct}"
personal="$(awk '/^[[:space:]]*location /{loc=$0; open=1; next}
  open && /proxy-cache\.conf/ && loc ~ /ics\/p/{print loc}
  open && /^[[:space:]]*}/{open=0}' web/nginx.conf)"
[[ -z "${personal}" ]] || fail "personal calendar location is cached: ${personal}"
secret='ics/p|abo|bestaetigen|api/public/subscriptions|api/public/altcha'
cached="$(awk -v re="${secret}" '/^[[:space:]]*location /{loc=$0; open=1; next}
  open && /proxy-cache\.conf/ && loc ~ re{print loc}
  open && /^[[:space:]]*}/{open=0}' web/nginx.conf)"
[[ -z "${cached}" ]] || fail "location with a secret in its URL or header is cached: ${cached}"
unredacted="$(awk '/^[[:space:]]*location /{loc=$0; open=1; ok=0; next}
  open && /ev_token_redacted|ev_ics_redacted/{ok=1}
  open && /^[[:space:]]*}/{if (loc ~ /abo|bestaetigen/ && !ok) print loc; open=0}' web/nginx.conf)"
[[ -z "${unredacted}" ]] || fail "token page location without a redacted access_log: ${unredacted}"

grep -Eq '^    access_log /var/log/nginx/access\.log ev_noquery;' web/nginx.conf || fail "server access_log must use ev_noquery"
odd="$(awk '/^[[:space:]]*location /{loc=$0} /access_log/ && !/access_log off/ && !/ev_noquery/ && !(/ev_ics_redacted/ && loc ~ /ics\/p/) && !(/ev_token_redacted/ && loc ~ /abo|bestaetigen/){print loc ": " $0}' web/nginx.conf)"
[[ -z "${odd}" ]] || fail "access_log with another format: ${odd}"

[[ "$(jq '[.services[].ports[]? | select(.target == 80)] | length' <<<"${cfg}")" -le 1 ]] || fail "port 80 published more than once"
[[ "$(jq -r '.services.web.volumes[].target' <<<"${cfg}" | grep -c proxy-cache.conf)" == 1 ]] || fail "web must mount proxy-cache.conf"

if grep -nE 'docker (system|image|volume|container|builder) prune' *.sh ../.github/workflows/*.yml; then
  fail "prune in scripts or workflows"
fi

[[ "${failed}" == 0 ]] && echo "compose-lint ok"
exit "${failed}"
