#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"

cd "${PROJECT_ROOT}"

echo "====================================================="
echo "   PartsOps AI Manager — Staging Stack Launcher"
echo "====================================================="

if [[ ! -f .env.staging ]]; then
  echo "ERROR: .env.staging file not found!" >&2
  exit 1
fi

COMPOSE=(docker compose --env-file .env.staging -f docker-compose.staging.yml)

if ! "${COMPOSE[@]}" config --quiet; then
  echo "ERROR: .env.staging is incomplete. Add the required compose bootstrap variables before starting staging." >&2
  exit 1
fi

echo "--> Launching Docker Staging Services (PostgreSQL 16, Keycloak, MinIO)..."
"${COMPOSE[@]}" up -d --wait postgres keycloak minio minio-init

echo "--> Staging dependencies are healthy."
"${COMPOSE[@]}" ps

echo "--> Executing Alembic database migrations in the staging backend..."
"${COMPOSE[@]}" up -d --wait backend-staging
"${COMPOSE[@]}" exec -T backend-staging python -m alembic upgrade head

echo "--> Starting durable pipeline worker..."
"${COMPOSE[@]}" up -d pipeline-worker-staging

echo "--> Running Beta Staging Verification Gate..."
"${COMPOSE[@]}" exec -T backend-staging bash scripts/verify_beta_staging.sh

echo "====================================================="
echo " SUCCESS: Staging environment initialized and verified!"
echo " Keycloak Admin Console: http://localhost:8080"
echo " MinIO S3 Console:       http://localhost:9001"
echo " PostgreSQL Endpoint:   localhost:5432"
echo "====================================================="
