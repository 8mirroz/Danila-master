#!/usr/bin/env bash
set -euo pipefail

required=(
  DATABASE_URL
  PARTSOPS_OIDC_ISSUER
  PARTSOPS_OIDC_AUDIENCE
  PARTSOPS_S3_BUCKET
  PARTSOPS_OUTBOUND_WEBHOOK_SECRET
  ERP_WEBHOOK_SECRET
)

for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "missing required staging variable: ${name}" >&2
    exit 1
  fi
done

[[ "${PARTSOPS_ENV:-}" == "production" ]] || { echo "PARTSOPS_ENV must be production" >&2; exit 1; }
[[ "${PARTSOPS_AUTH_MODE:-}" == "oidc" ]] || { echo "PARTSOPS_AUTH_MODE must be oidc" >&2; exit 1; }
[[ "${PARTSOPS_STORAGE_BACKEND:-}" == "s3" ]] || { echo "PARTSOPS_STORAGE_BACKEND must be s3" >&2; exit 1; }
[[ "${DATABASE_URL}" == postgresql://* || "${DATABASE_URL}" == postgres://* || "${DATABASE_URL}" == postgresql+psycopg://* ]] || { echo "DATABASE_URL must be PostgreSQL" >&2; exit 1; }

PYTHON_BIN="python3"
if [[ -x "./venv/bin/python" ]]; then
  PYTHON_BIN="./venv/bin/python"
fi

"${PYTHON_BIN}" -m alembic upgrade head
"${PYTHON_BIN}" - <<'PY'
from settings import settings
settings.validate_auth_configuration()
print("production configuration validated")
PY

if [[ -n "${PARTSOPS_STAGING_HEALTH_URL:-}" ]]; then
  curl --fail --silent --show-error "${PARTSOPS_STAGING_HEALTH_URL%/}/health" >/dev/null
  echo "staging health endpoint passed"
fi

echo "beta staging gate passed"
