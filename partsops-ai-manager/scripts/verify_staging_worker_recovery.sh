#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

COMPOSE=(docker-compose --env-file .env.staging -f docker-compose.staging.yml)
if [[ "${PARTSOPS_DOCKER_COMPOSE:-}" == "docker compose" ]]; then
  COMPOSE=(docker compose --env-file .env.staging -f docker-compose.staging.yml)
fi

"${COMPOSE[@]}" stop pipeline-worker-staging >/dev/null
proof="$("${COMPOSE[@]}" exec -T backend-staging python scripts/verify_staging_worker_recovery.py prepare)"
read -r tenant_id request_id run_id < <(
  printf '%s' "${proof}" | ./venv/bin/python -c 'import json, sys; payload = json.load(sys.stdin); print(payload["tenant_id"], payload["request_id"], payload["run_id"])'
)

cleanup() {
  "${COMPOSE[@]}" exec -T backend-staging python scripts/verify_staging_worker_recovery.py cleanup \
    --tenant-id "${tenant_id}" --request-id "${request_id}" --run-id "${run_id}" >/dev/null || true
}
trap cleanup EXIT

"${COMPOSE[@]}" start pipeline-worker-staging >/dev/null
for _attempt in $(seq 1 30); do
  set +e
  output="$("${COMPOSE[@]}" exec -T backend-staging python scripts/verify_staging_worker_recovery.py verify \
    --tenant-id "${tenant_id}" --run-id "${run_id}" 2>&1)"
  status=$?
  set -e
  if [[ ${status} -eq 0 ]]; then
    printf '%s\n' "${output}"
    exit 0
  fi
  if [[ "${output}" != "staging_worker_recovery=pending" ]]; then
    printf '%s\n' "${output}" >&2
    exit ${status}
  fi
  sleep 1
done

echo "Timed out waiting for worker recovery proof" >&2
exit 1
