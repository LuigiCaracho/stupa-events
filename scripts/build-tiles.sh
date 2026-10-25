#!/usr/bin/env bash
# Builds the map data of the stack from the pins in deploy/tiles.lock. The ONLY place that downloads
# anything for the maps (PMTiles extracts of a pinned Protomaps daily build, the pmtiles CLI as a
# fallback, glyphs and sprites). Tiles are never committed: deploy/tiles/ is gitignored, the
# production copy lives in the volume tiles_data.
# Usage: scripts/build-tiles.sh [fetch|verify|install|assets|bump <YYYYMMDD>]
#   fetch    extract world (zoom 0-5) and the Reutlingen region (zoom 0-15) into deploy/tiles/ (default)
#   verify   check the files against the SHA-256 in tiles.lock, offline
#   install  copy deploy/tiles/*.pmtiles into the compose volume tiles_data, then verify there
#   assets   fetch glyphs and sprites at the pinned commit into frontend/public/map-style/
#   bump     pin a new daily build (the Protomaps bucket keeps about a week), rewrite the checksums
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
lock="${root}/deploy/tiles.lock"
out="${root}/deploy/tiles"
style_dir="${root}/frontend/public/map-style"
glyph_ranges=(0-255 256-511 7680-7935 8192-8447 8448-8703)
glyph_fonts=("Noto Sans Regular" "Noto Sans Medium" "Noto Sans Italic")

die() { echo "build-tiles: $*" >&2; exit 1; }
load_lock() { set -a; . "${lock}"; set +a; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
set_pin() { sed -i "s|^$1=.*|$1=$2|" "${lock}"; }

find_pmtiles() {
  local bin
  bin="$(command -v pmtiles || true)"
  [[ -n "${bin}" ]] || bin="$(nix build --no-link --print-out-paths nixpkgs#pmtiles 2>/dev/null | head -1)/bin/pmtiles" || true
  if [[ ! -x "${bin}" ]]; then
    local dir="${out}/.bin"
    mkdir -p "${dir}"
    local tgz="${dir}/pmtiles.tar.gz"
    curl -fsSL -o "${tgz}" "https://github.com/protomaps/go-pmtiles/releases/download/v${PMTILES_VERSION}/go-pmtiles_${PMTILES_VERSION}_Linux_x86_64.tar.gz"
    [[ "$(sha "${tgz}")" == "${PMTILES_RELEASE_SHA256}" ]] || die "pmtiles release checksum mismatch"
    tar -xzf "${tgz}" -C "${dir}" pmtiles
    rm -f "${tgz}"
    bin="${dir}/pmtiles"
  fi
  "${bin}" version | grep -q "pmtiles ${PMTILES_VERSION}\b" || die "pmtiles ${PMTILES_VERSION} required, got: $("${bin}" version)"
  echo "${bin}"
}

extract() {
  local pmtiles="$1" name="$2" expected="$3"; shift 3
  local part="${out}/${name}.pmtiles.part"
  rm -f "${part}"
  local log="${out}/.extract.log"
  if ! "${pmtiles}" extract "${PROTOMAPS_URL}" "${part}" "$@" >"${log}" 2>&1; then
    rm -f "${part}"
    cat "${log}" >&2
    grep -q '404' "${log}" && die "Build abgelaufen: run 'scripts/build-tiles.sh bump <YYYYMMDD>' with a current build"
    die "extract of ${name} failed"
  fi
  "${pmtiles}" verify "${part}" >/dev/null || { rm -f "${part}"; die "pmtiles verify failed for ${name}"; }
  if [[ "$(sha "${part}")" != "${expected}" ]]; then
    local got
    got="$(sha "${part}")"
    rm -f "${part}"
    die "${name}: SHA-256 ${got} differs from tiles.lock (${expected})"
  fi
  mv "${part}" "${out}/${name}.pmtiles"
  echo "${name}.pmtiles ok ($(stat -c %s "${out}/${name}.pmtiles") bytes)"
}

fetch() {
  mkdir -p "${out}"
  local pmtiles
  pmtiles="$(find_pmtiles)"
  extract "${pmtiles}" world "${WORLD_SHA256}" --maxzoom="${WORLD_MAXZOOM}"
  extract "${pmtiles}" "${REGION_NAME}" "${REGION_SHA256}" --bbox="${REGION_BBOX}" --maxzoom="${REGION_MAXZOOM}"
  rm -f "${out}/.extract.log"
}

verify_dir() {
  local dir="$1" failed=0
  for pair in "world:${WORLD_SHA256}" "${REGION_NAME}:${REGION_SHA256}"; do
    local file="${dir}/${pair%%:*}.pmtiles"
    [[ -f "${file}" ]] || { echo "missing ${file}" >&2; failed=1; continue; }
    [[ "$(sha "${file}")" == "${pair#*:}" ]] && echo "${file##*/} ok" || { echo "${file##*/}: checksum differs" >&2; failed=1; }
  done
  return "${failed}"
}

install_volume() {
  verify_dir "${out}"
  local volume="${COMPOSE_PROJECT_NAME:-stupa-events}_tiles_data"
  docker volume create "${volume}" >/dev/null
  docker run --rm -v "${volume}:/t" -v "${out}:/src:ro" alpine:3 sh -c 'cp /src/*.pmtiles /t/ && chmod 644 /t/*.pmtiles'
  local check
  check="$(mktemp -d)"
  trap "rm -rf '${check}'" EXIT
  docker run --rm -v "${volume}:/t:ro" -v "${check}:/o" alpine:3 sh -c 'cp /t/*.pmtiles /o/ && chmod -R a+r /o'
  verify_dir "${check}"
}

bump() {
  local build="${1:?usage: bump <YYYYMMDD>}"
  [[ "${build}" =~ ^[0-9]{8}$ ]] || die "build must be YYYYMMDD"
  local url="${PROTOMAPS_URL//${PROTOMAPS_BUILD}/${build}}"
  local old_world="" old_region=""
  [[ -f "${out}/world.pmtiles" ]] && old_world="$(stat -c %s "${out}/world.pmtiles")"
  [[ -f "${out}/${REGION_NAME}.pmtiles" ]] && old_region="$(stat -c %s "${out}/${REGION_NAME}.pmtiles")"
  mkdir -p "${out}"
  local pmtiles tmp
  pmtiles="$(find_pmtiles)"
  tmp="$(mktemp -d)"
  trap "rm -rf '${tmp}'" EXIT
  "${pmtiles}" extract "${url}" "${tmp}/world.pmtiles" --maxzoom="${WORLD_MAXZOOM}"
  "${pmtiles}" extract "${url}" "${tmp}/region.pmtiles" --bbox="${REGION_BBOX}" --maxzoom="${REGION_MAXZOOM}"
  local world_sha region_sha
  world_sha="$(sha "${tmp}/world.pmtiles")"
  region_sha="$(sha "${tmp}/region.pmtiles")"
  set_pin PROTOMAPS_BUILD "${build}"
  set_pin WORLD_SHA256 "${world_sha}"
  set_pin REGION_SHA256 "${region_sha}"
  echo "world: ${old_world:-?} -> $(stat -c %s "${tmp}/world.pmtiles") bytes, region: ${old_region:-?} -> $(stat -c %s "${tmp}/region.pmtiles") bytes"
  echo "tiles.lock updated; review the diff, then run: scripts/build-tiles.sh fetch"
}

assets() {
  local dir tgz src
  dir="$(mktemp -d)"
  trap "rm -rf '${dir}'" EXIT
  tgz="${dir}/assets.tar.gz"
  curl -fsSL -o "${tgz}" "https://github.com/${ASSETS_REPO}/archive/${ASSETS_COMMIT}.tar.gz"
  if [[ -z "${ASSETS_SHA256}" ]]; then
    set_pin ASSETS_SHA256 "$(sha "${tgz}")"
    echo "ASSETS_SHA256 pinned in tiles.lock; review and commit it"
  else
    [[ "$(sha "${tgz}")" == "${ASSETS_SHA256}" ]] || die "assets tarball checksum mismatch"
  fi
  tar -xzf "${tgz}" -C "${dir}"
  src="${dir}/$(basename "${ASSETS_REPO}")-${ASSETS_COMMIT}"
  for font in "${glyph_fonts[@]}"; do
    mkdir -p "${style_dir}/fonts/${font}"
    for range in "${glyph_ranges[@]}"; do
      cp "${src}/fonts/${font}/${range}.pbf" "${style_dir}/fonts/${font}/"
    done
  done
  cp "${src}/fonts/OFL.txt" "${style_dir}/fonts/OFL.txt"
  mkdir -p "${style_dir}/sprites/v4"
  for theme in light dark; do
    for suffix in "" "@2x"; do
      cp "${src}/sprites/v4/${theme}${suffix}".{json,png} "${style_dir}/sprites/v4/"
    done
  done
  echo "glyphs and sprites copied to ${style_dir#"${root}/"}"
}

load_lock
case "${1:-fetch}" in
  fetch) fetch ;;
  verify) verify_dir "${out}" ;;
  install) install_volume ;;
  assets) assets ;;
  bump) bump "${2:-}" ;;
  *) die "unknown mode '$1'" ;;
esac
