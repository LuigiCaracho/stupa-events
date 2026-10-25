#!/usr/bin/env bash
# Stack of pwa-update.spec: a writable copy of the production build behind the throwaway nginx on port 8084. The spec
# edits the copy (`index.html` and the hash in `ngsw.json`) to publish a "new version".
#   pwa-update-stack.sh start | reset | stop
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
dist="${here}/../dist/stupa-events/browser"
copy="${PWA_DIST:-/tmp/ev-pwa-dist}"
port=8084

case "${1:?start|reset|stop}" in
  start | reset)
    rm -rf "${copy}"
    cp -r "${dist}" "${copy}"
    "${here}/e2e-web.sh" down "${port}"
    "${here}/e2e-web.sh" up "${port}" "${copy}" "${here}/../e2e/fixtures/tiles"
    ;;
  stop)
    "${here}/e2e-web.sh" down "${port}"
    rm -rf "${copy}"
    ;;
  *)
    echo "usage: $0 start|reset|stop" >&2
    exit 2
    ;;
esac
