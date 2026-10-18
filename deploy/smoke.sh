#!/usr/bin/env bash
# Compose smoke test (PLAN 12.4): /api/health answers 200 and every nginx location carries the
# Content-Security-Policy. Probes a running stack, starts nothing.
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
  /sitemap.xml
  /robots.txt
  /manifest.webmanifest
  /api/events/00000000-0000-0000-0000-000000000000/poster
  /api/events/00000000-0000-0000-0000-000000000000/attachments
)

status="$(curl -s -o /dev/null -w '%{http_code}' "${base}/api/health")"
[[ "${status}" == 200 ]] || { echo "/api/health: ${status}" >&2; exit 1; }

failed=0
for path in "${paths[@]}"; do
  if ! curl -s -o /dev/null -D - "${base}${path}" | grep -qi '^content-security-policy:.*default-src'; then
    echo "no CSP on ${path}" >&2
    failed=1
  fi
done
[[ "${failed}" == 0 ]] && echo "smoke ok (${#paths[@]} locations)"
exit "${failed}"
