#!/usr/bin/env sh
set -eu

: "${STAGING_BASE_URL:?STAGING_BASE_URL is required}"

health_payload="$(curl --fail --silent --show-error --max-time 20 \
  "${STAGING_BASE_URL}/api/health")"
printf '%s' "${health_payload}" | grep -q '"frontend":"healthy"'
printf '%s' "${health_payload}" | grep -q '"backend":"healthy"'

if [ "${RUN_RESEARCH_SMOKE:-false}" = "true" ]; then
  : "${APP_PASSWORD:?APP_PASSWORD is required for the authenticated smoke test}"
  cookie_file="$(mktemp)"
  trap 'rm -f "${cookie_file}"' EXIT
  curl --fail --silent --show-error --max-time 20 \
    --cookie-jar "${cookie_file}" \
    --header "Content-Type: application/json" \
    --header "Origin: ${STAGING_BASE_URL}" \
    --data "{\"password\":\"${APP_PASSWORD}\"}" \
    "${STAGING_BASE_URL}/api/auth/login" >/dev/null
  curl --fail --silent --show-error --no-buffer --max-time 600 \
    --cookie "${cookie_file}" \
    --header "Content-Type: application/json" \
    --header "Origin: ${STAGING_BASE_URL}" \
    --data '{"inquiry":"Welche Primärquellen definieren HTTP Semantik?","model":"mercury","mode":"quick"}' \
    "${STAGING_BASE_URL}/api/research-runs/stream" | grep -q '"type":"run.completed"'
fi

