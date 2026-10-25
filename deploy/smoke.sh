#!/usr/bin/env bash
# Compose smoke test (PLAN 12.4): /api/health answers 200, every nginx location carries the
# Content-Security-Policy, and each of the five security headers appears exactly once per path
# (the API sets them too, nginx hides its copy). Probes a running stack, starts nothing.
# Usage: deploy/smoke.sh [base-url]   (default http://127.0.0.1:8081)
set -euo pipefail

base="${1:-http://127.0.0.1:8081}"
paths=(
  /healthz /
  /deep/spa/route
  /api/health
  /api/public/feed/events
  /ics/all.ics
  /ics/p/probe
  /e/probe
  /k/probe
  /suche
  /kalender
  /rueckblick
  /start
  /abos
  /abo
  /abo/probe
  /bestaetigen
  /bestaetigen/probe
  /api/public/getstarted/questions
  /ics/e/probe.ics
  /sitemap.xml
  /robots.txt
  /manifest.webmanifest
  /karte
  /campus
  /tiles/world.pmtiles
  /map/maplibre-gl-worker.mjs
  /map-style/style-light.json
  /api/events/00000000-0000-0000-0000-000000000000/poster
  /api/events/00000000-0000-0000-0000-000000000000/attachments
)

status="$(curl -s -o /dev/null -w '%{http_code}' "${base}/api/health")"
[[ "${status}" == 200 ]] || { echo "/api/health: ${status}" >&2; exit 1; }

security_headers=(content-security-policy permissions-policy referrer-policy x-content-type-options x-frame-options)

failed=0
for path in "${paths[@]}"; do
  headers="$(curl -s -o /dev/null -D - "${base}${path}")"
  if ! grep -qi '^content-security-policy:.*default-src' <<<"${headers}"; then
    echo "no CSP on ${path}" >&2
    failed=1
  fi
  for name in "${security_headers[@]}"; do
    count="$(grep -ci "^${name}:" <<<"${headers}" || true)"
    if [[ "${count}" != 1 ]]; then
      echo "${name} appears ${count} times on ${path}" >&2
      failed=1
    fi
  done
done
[[ "${failed}" == 0 ]] && echo "smoke ok (${#paths[@]} locations)"
exit "${failed}"
