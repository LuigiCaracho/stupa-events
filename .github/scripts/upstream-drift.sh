#!/usr/bin/env bash
# Upstream drift report: lists files of PROVENANCE.json whose upstream version changed between
# the pinned commit and the upstream default branch. Prints Markdown, exit 0 either way; the
# workflow opens an issue when the output is non-empty. Needs git, jq, sha256sum.
# Usage: upstream-drift.sh <provenance.json> <upstream-clone-dir>
set -euo pipefail

provenance="${1:?provenance.json}"
clone="${2:?upstream clone dir}"
pinned="$(jq -r .upstream.commit "${provenance}")"
head="$(git -C "${clone}" rev-parse HEAD)"

hash_at() { git -C "${clone}" show "$1:$2" 2>/dev/null | sha256sum | cut -d' ' -f1; }

drifted=()
while IFS=$'\t' read -r path source mode; do
  [[ "$(hash_at "${pinned}" "${source}")" == "$(hash_at "${head}" "${source}")" ]] \
    || drifted+=("| \`${path}\` | \`${source}\` | ${mode} |")
done < <(jq -r '.files[] | [.path, .source, .mode] | @tsv' "${provenance}")

[[ "${#drifted[@]}" -gt 0 ]] || exit 0
echo "Upstream \`$(jq -r .upstream.repo "${provenance}")\` moved from \`${pinned:0:7}\` to \`${head:0:7}\`. ${#drifted[@]} copied file(s) changed upstream:"
echo
echo "| Local file | Upstream source | Mode |"
echo "|---|---|---|"
printf '%s\n' "${drifted[@]}"
echo
echo "Review each diff with \`git diff ${pinned:0:7} ${head:0:7} -- <source>\`, port what matters, then bump \`upstream.commit\`."
