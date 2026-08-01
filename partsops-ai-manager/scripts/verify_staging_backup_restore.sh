#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

BASE_COMPOSE=(docker-compose --env-file .env.staging -f docker-compose.staging.yml)
VERIFY_COMPOSE=(docker-compose --env-file .env.staging -f docker-compose.staging.yml -f docker-compose.backup-verify.yml)
if [[ "${PARTSOPS_DOCKER_COMPOSE:-}" == "docker compose" ]]; then
  BASE_COMPOSE=(docker compose --env-file .env.staging -f docker-compose.staging.yml)
  VERIFY_COMPOSE=(docker compose --env-file .env.staging -f docker-compose.staging.yml -f docker-compose.backup-verify.yml)
fi

temporary_dir="$(mktemp -d "${TMPDIR:-/tmp}/partsops-backup-restore.XXXXXX")"
archive_path="${temporary_dir}/partsops.dump"

cleanup() {
  "${VERIFY_COMPOSE[@]}" rm -sfv postgres-restore-proof >/dev/null 2>&1 || true
  rm -f "${archive_path}"
  rmdir "${temporary_dir}" 2>/dev/null || true
}
trap cleanup EXIT

"${VERIFY_COMPOSE[@]}" up -d --wait postgres-restore-proof >/dev/null
"${BASE_COMPOSE[@]}" exec -T postgres sh -lc 'pg_dump -U "$POSTGRES_USER" --format=custom "$POSTGRES_DB"' >"${archive_path}"
"${VERIFY_COMPOSE[@]}" exec -T postgres-restore-proof sh -lc 'pg_restore -U "$POSTGRES_USER" --no-owner --no-privileges --dbname="$POSTGRES_DB"' <"${archive_path}"

count_query='SELECT (SELECT COUNT(*) FROM organization), (SELECT COUNT(*) FROM partrequest), (SELECT COUNT(*) FROM pipelinerun), (SELECT COUNT(*) FROM erpsynclog), (SELECT COUNT(*) FROM uploadartifact);'
source_counts="$("${BASE_COMPOSE[@]}" exec -T postgres sh -lc "psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -At -F, -c \"${count_query}\"")"
restored_counts="$("${VERIFY_COMPOSE[@]}" exec -T postgres-restore-proof sh -lc "psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -At -F, -c \"${count_query}\"")"
source_revision="$("${BASE_COMPOSE[@]}" exec -T postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "SELECT version_num FROM alembic_version"')"
restored_revision="$("${VERIFY_COMPOSE[@]}" exec -T postgres-restore-proof sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "SELECT version_num FROM alembic_version"')"

if [[ "${source_counts}" != "${restored_counts}" || "${source_revision}" != "${restored_revision}" ]]; then
  echo "Backup restore validation mismatch" >&2
  exit 1
fi

echo "staging_backup_restore=passed clean_postgres=1 schema=1 data_counts=matched"
