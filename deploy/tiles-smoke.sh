#!/usr/bin/env bash
# Tile smoke test: the PMTiles archives behind nginx answer Range requests the way the pmtiles client needs
# them (206 with Content-Range, Accept-Ranges on HEAD, no Content-Encoding, strong ETag, 7 day Cache-Control, exactly
# one CSP), and POST is refused. Probes a running stack, starts nothing.
# Usage: deploy/tiles-smoke.sh [base-url]   (default http://127.0.0.1:8081)
set -euo pipefail

base="${1:-http://127.0.0.1:8081}"
failed=0
fail() { echo "tiles-smoke: $*" >&2; failed=1; }
header() { grep -i "^$1:" <<<"$2" | head -1 | cut -d' ' -f2- | tr -d '\r'; }

for file in world reutlingen; do
  url="${base}/tiles/${file}.pmtiles"
  headers="$(curl -s -o /dev/null -D - -H 'Range: bytes=0-16383' "${url}")"
  grep -q '^HTTP/[0-9.]* 206' <<<"${headers}" || fail "${file}: Range request is not 206"
  [[ "$(header content-range "${headers}")" == bytes\ 0-16383/* ]] || fail "${file}: Content-Range wrong"
  [[ "$(header content-length "${headers}")" == 16384 ]] || fail "${file}: Content-Length is not 16384"
  head_headers="$(curl -sI "${url}")"
  [[ "$(grep -ci '^accept-ranges: bytes' <<<"${head_headers}" || true)" == 1 ]] || fail "${file}: HEAD must advertise Accept-Ranges bytes once"
  [[ -z "$(header content-encoding "${headers}")" ]] || fail "${file}: Content-Encoding must be absent"
  etag="$(header etag "${headers}")"
  [[ -n "${etag}" && "${etag}" != W/* ]] || fail "${file}: ETag missing or weak (${etag})"
  [[ "$(header cache-control "${headers}")" == *max-age=604800* ]] || fail "${file}: Cache-Control is not 7 days"
  [[ "$(grep -ci '^content-security-policy:' <<<"${headers}" || true)" == 1 ]] || fail "${file}: CSP must appear once"
  magic="$(curl -s -H 'Range: bytes=0-6' "${url}" | head -c 7)"
  [[ "${magic}" == PMTiles ]] || fail "${file}: archive does not start with PMTiles (${magic})"
done

[[ "$(curl -s -o /dev/null -w '%{http_code}' -X POST "${base}/tiles/world.pmtiles")" == 405 || \
   "$(curl -s -o /dev/null -w '%{http_code}' -X POST "${base}/tiles/world.pmtiles")" == 403 ]] || fail "POST on /tiles/ is not refused"
[[ "$(curl -s -o /dev/null -w '%{http_code}' "${base}/tiles/missing.pmtiles")" == 404 ]] || fail "unknown archive is not 404"

[[ "${failed}" == 0 ]] && echo "tiles-smoke ok"
exit "${failed}"
