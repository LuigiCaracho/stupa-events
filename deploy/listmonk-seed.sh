#!/usr/bin/env bash
# Seed the dev Listmonk idempotently: SMTP to Mailpit, a restricted role and the API user
# `events-api` (token written to backend/.env when missing), and the list `events-alle`.
# Listmonk hands out an API token only at creation, so a user without a token in the env file is
# deleted and created again. Needs the stack from docker-compose.dev.yml and curl, jq.
# Env: LISTMONK_URL (http://127.0.0.1:9002), LISTMONK_ADMIN_USER/PASSWORD (dev defaults), ENV_FILE.
set -euo pipefail

R="$(cd "$(dirname "$0")/.." && pwd)"
url="${LISTMONK_URL:-http://127.0.0.1:9002}"
admin="${LISTMONK_ADMIN_USER:-admin}"
password="${LISTMONK_ADMIN_PASSWORD:-dev-listmonk-admin}"
env_file="${ENV_FILE:-$R/backend/.env}"
jar="$(mktemp)"
trap 'rm -f "$jar"' EXIT

wait_healthy() {
  for _ in $(seq 1 60); do
    curl -fs -o /dev/null "$url/health" && return 0
    sleep 2
  done
  echo "listmonk-seed: $url/health did not answer" >&2
  return 1
}

login() {
  local nonce
  nonce="$(curl -fsS -c "$jar" "$url/admin/login" | grep -o 'name="nonce" value="[^"]*' | sed 's/.*value="//')"
  curl -fsS -b "$jar" -c "$jar" -o /dev/null \
    --data-urlencode "nonce=$nonce" --data-urlencode "next=/admin" \
    --data-urlencode "username=$admin" --data-urlencode "password=$password" "$url/admin/login"
}

api() { curl -fsS -b "$jar" -H 'Content-Type: application/json' "$@"; }

seed_smtp() {
  local settings
  settings="$(api "$url/api/settings" | jq '.data')"
  [[ "$(jq -r '.smtp[0].host' <<<"$settings")" == mailpit ]] && return 0
  jq '.smtp[0] |= (.host = "mailpit" | .port = 1025 | .auth_protocol = "none" | .username = ""
      | .password = "" | .tls_type = "none" | .enabled = true)
      | .["app.root_url"] = "http://127.0.0.1:9002" | .["app.from_email"] = "STUPA Events <events@example.test>"
      | .["app.send_optin_confirmation"] = false' <<<"$settings" |
    api -X PUT --data-binary @- "$url/api/settings" >/dev/null
  sleep 3
  wait_healthy
  login
}

role_id() {
  local id
  id="$(api "$url/api/roles/users" | jq '.data[] | select(.name == "events-api") | .id')"
  [[ -n "$id" ]] && { echo "$id"; return; }
  api -X POST "$url/api/roles/users" -d '{"name":"events-api","permissions":[
    "subscribers:get","subscribers:get_all","subscribers:manage",
    "campaigns:get","campaigns:get_all","campaigns:manage","campaigns:manage_all",
    "lists:get_all","lists:manage_all"]}' | jq '.data.id'
}

seed_api_user() {
  local user_id
  user_id="$(api "$url/api/users" | jq '.data[] | select(.username == "events-api") | .id')"
  if [[ -n "$user_id" ]] && grep -q '^LISTMONK_API_TOKEN=.\+' "$env_file" 2>/dev/null; then
    return 0
  fi
  [[ -n "$user_id" ]] && api -X DELETE "$url/api/users/$user_id" >/dev/null
  local token
  token="$(api -X POST "$url/api/users" -d "{\"username\":\"events-api\",\"name\":\"STUPA Events API\",
    \"type\":\"api\",\"status\":\"enabled\",\"user_role_id\":$(role_id),\"list_role_id\":null}" | jq -r '.data.password')"
  touch "$env_file"
  sed -i '/^LISTMONK_API_USER=/d;/^LISTMONK_API_TOKEN=/d' "$env_file"
  printf 'LISTMONK_API_USER=events-api\nLISTMONK_API_TOKEN=%s\n' "$token" >>"$env_file"
}

seed_all_list() {
  [[ "$(api "$url/api/lists?query=events-alle&per_page=all" | jq '[.data.results[] | select(.name == "events-alle")] | length')" != 0 ]] && return 0
  api -X POST "$url/api/lists" -d '{"name":"events-alle","type":"private","optin":"single","tags":["events"]}' >/dev/null
}

wait_healthy
login
seed_smtp
seed_api_user
seed_all_list
echo "listmonk-seed: ok"
