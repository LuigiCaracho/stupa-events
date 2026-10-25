#!/usr/bin/env bash
# Throwaway nginx with the production config in front of the host API, for the PWA and map specs (a service worker
# needs the production build and the production headers, `ng serve` has neither). Starts nothing but one container.
#   e2e-web.sh up    <port> <dist-dir> <tiles-dir>   (the API runs on 127.0.0.1:8000)
#   e2e-web.sh down  <port>
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
action="${1:?up|down}"
port="${2:?port}"
name="ev-web-${port}"

case "${action}" in
  up)
    dist="$(realpath "${3:?dist dir}")"
    tiles="$(realpath "${4:?tiles dir}")"
    conf="$(mktemp -d)"
    sed "s/listen 80;/listen ${port};/" "${root}/deploy/web/nginx.conf" >"${conf}/default.conf"
    if grep -q 'geolocation=()' "${root}/deploy/web/security-headers.conf"; then
      echo "e2e-web: deploy/web/security-headers.conf still has geolocation=(); the map specs run with geolocation=(self)" >&2
    fi
    sed 's/geolocation=()/geolocation=(self)/' "${root}/deploy/web/security-headers.conf" >"${conf}/security-headers.conf"
    docker rm -f "${name}" >/dev/null 2>&1 || true
    docker run -d --rm --name "${name}" --network host --add-host api:127.0.0.1 \
      -e TRUSTED_PROXY_IP=192.0.2.1 \
      -v "${conf}/default.conf:/etc/nginx/conf.d/default.conf:ro" \
      -v "${root}/deploy/web/real-ip.conf.template:/etc/nginx/templates/real-ip.conf.template:ro" \
      -v "${conf}/security-headers.conf:/etc/nginx/snippets/security-headers.conf:ro" \
      -v "${root}/deploy/web/api-proxy.conf:/etc/nginx/snippets/api-proxy.conf:ro" \
      -v "${root}/deploy/web/proxy-cache.conf:/etc/nginx/snippets/proxy-cache.conf:ro" \
      -v "${dist}:/usr/share/nginx/html:ro" \
      -v "${tiles}:/usr/share/nginx/tiles:ro" \
      nginx:1.27-alpine >/dev/null
    for _ in $(seq 1 30); do
      curl -fsS "http://127.0.0.1:${port}/healthz" >/dev/null 2>&1 && { echo "http://127.0.0.1:${port}"; exit 0; }
      sleep 0.5
    done
    docker logs "${name}" >&2
    exit 1
    ;;
  down)
    docker rm -f "${name}" >/dev/null 2>&1 || true
    ;;
  *)
    echo "usage: $0 up <port> <dist> <tiles> | down <port>" >&2
    exit 2
    ;;
esac
