#!/usr/bin/env bash
# Public smoke test (B1 contract 6.3): link previews, cookie freedom, bundle parity, log hygiene and the
# proxy cache, against a running compose stack (web on 127.0.0.1:8081). It needs one public event with a
# poster; without one it says so and fails. Starts nothing.
# Usage: deploy/public-smoke.sh [base-url]   (default http://127.0.0.1:8081)
# Env: COMPOSE (the compose command for the log probe; default uses deploy/docker-compose.yml with .env.dev)
set -euo pipefail

base="${1:-http://127.0.0.1:8081}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
compose=${COMPOSE:-"docker compose -f ${here}/docker-compose.yml --env-file ${here}/.env.dev"}
tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
failed=0
fail() { echo "public-smoke: $*" >&2; failed=1; }

slug="$(curl -fsS "${base}/api/public/events?limit=50" | jq -r '[.items[] | select(.image != null)][0].slug // empty')"
[[ -n "${slug}" ]] || { echo "public-smoke: no public event with a poster in the stack; publish one first" >&2; exit 2; }

agents=("WhatsApp/2.24.1" "Synapse (bot; +https://github.com/element-hq/synapse)" "facebookexternalhit/1.1" "Signal-Desktop/7.0")
for i in "${!agents[@]}"; do
  curl -fsS -A "${agents[$i]}" -D "${tmp}/h$i" -o "${tmp}/b$i" "${base}/e/${slug}" || fail "GET /e/${slug} as ${agents[$i]}"
done
body="${tmp}/b0"
for prop in og:title og:description og:image og:url; do
  grep -Eq "<meta property=\"${prop}\" content=\"[^\"]+\"" "${body}" || fail "no ${prop}"
done
image="$(grep -Eo '<meta property="og:image" content="[^"]+"' "${body}" | sed 's/.*content="//; s/"$//')"
[[ "${image}" == *"-og_1200x630.webp" ]] || fail "og:image is not the 1200x630 derivative: ${image}"
path="/${image#*://*/}"
read -r code kind < <(curl -sS -o /dev/null -w '%{http_code} %{content_type}\n' "${base}${path}")
[[ "${code} ${kind}" == "200 image/webp" ]] || fail "og:image answers ${code} ${kind}"
for i in 1 2 3; do cmp -s "${tmp}/b0" "${tmp}/b$i" || fail "body differs for ${agents[$i]}"; done

headers="${tmp}/h0"
[[ "$(grep -ci '^content-security-policy:' "${headers}")" == 1 ]] || fail "need exactly one Content-Security-Policy"
! grep -qi '^set-cookie:' "${headers}" || fail "Set-Cookie on the event page"
grep -Eqi '^cache-control:.*max-age=60' "${headers}" || fail "Cache-Control without max-age=60"
etag="$(grep -i '^etag:' "${headers}" | head -1 | cut -d' ' -f2- | tr -d '\r')"
[[ -n "${etag}" ]] || fail "no ETag"
code="$(curl -sS -o /dev/null -w '%{http_code}' -H "If-None-Match: ${etag}" "${base}/e/${slug}")"
[[ "${code}" == 304 ]] || fail "If-None-Match answered ${code}, not 304"

for path in / /suche /kalender /rueckblick /start /abos /sitemap.xml /robots.txt /api/public/events /api/public/today \
  /api/public/getstarted/questions "/ics/e/${slug}.ics" /api/auth/me; do
  code="$(curl -sS -o /dev/null -D "${tmp}/ck" -w '%{http_code}' "${base}${path}")"
  # Anonymous /api/auth/me is a 401 by design; the probe is about the missing cookie.
  [[ "${code}" == 2* || ( "${path}" == /api/auth/me && "${code}" == 401 ) ]] ||
    fail "${path} answered ${code} (rate limit?)"
  ! grep -qi '^set-cookie:' "${tmp}/ck" || fail "Set-Cookie on ${path}"
  sleep 0.3
done

bundles() { grep -Eo '(main|styles)-[A-Za-z0-9]+\.(js|css)' | sort -u; }
curl -fsS "${base}/e/${slug}" | bundles >"${tmp}/shell"
curl -fsS "${base}/index.html" | bundles >"${tmp}/static"
[[ -s "${tmp}/shell" ]] || fail "the shell names no bundles"
cmp -s "${tmp}/shell" "${tmp}/static" || fail "shell and /index.html name different bundles (api and web images differ)"

sleep 3  # the probes above use up the ev_page burst (10); let it drain so the next requests are not 429
secret="GEHEIM$RANDOM$RANDOM"
curl -fsS -o /dev/null "${base}/suche?q=${secret}"
curl -fsS -o /dev/null "${base}/api/public/events?q=${secret}"
if ${compose} logs --no-color web api 2>/dev/null | grep -q "${secret}"; then
  fail "the search text reached a container log"
fi

curl -fsS -o /dev/null "${base}/api/public/today"
status="$(curl -fsS -D - -o /dev/null "${base}/api/public/today" | grep -i '^x-cache-status:' | tr -d '\r' | awk '{print toupper($2)}')"
[[ "${status}" == "HIT" ]] || fail "the second /api/public/today was not served by the proxy cache (X-Cache-Status: ${status:-none})"

[[ "${failed}" == 0 ]] && echo "public-smoke ok (${slug})"
exit "${failed}"
