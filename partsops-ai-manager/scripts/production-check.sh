#!/usr/bin/env bash
# PartsOps AI Manager — Production Readiness Check
# Запускает: unit tests, postgres integration tests, rbac stress tests, secure upload tests, migration up/down/up

set -e
cd "$(dirname "$0")/.."

echo "=========================================="
echo "  PartsOps AI Manager — Production Check"
echo "=========================================="

# 1. Unit Tests (config, events, state machine, etc.)
echo ""
echo "[1/5] Running unit tests..."
venv/bin/python -m pytest tests/test_database_config.py tests/test_events.py tests/test_state_machine.py -v

# 2. RBAC Stress Tests
echo ""
echo "[2/5] Running RBAC isolation stress tests..."
venv/bin/python -m pytest tests/test_rbac_isolation_stress.py -v

# 3. Secure Upload Tests
echo ""
echo "[3/5] Running secure upload tests..."
venv/bin/python -m pytest tests/test_secure_upload.py -v

# 4. Migration Cycle (up → down → up) — requires Docker PostgreSQL
echo ""
echo "[4/5] Running Alembic migration cycle (up/down/up)..."
export DATABASE_URL="${DATABASE_URL:-postgresql://partsops:partsops_test_password@localhost:5433/partsops_test}"

# Start postgres if not running
if ! docker ps | grep -q partsops-postgres-test; then
    echo "Starting PostgreSQL Docker container..."
    docker compose -f docker-compose.postgres.yml up -d
    sleep 5
fi

venv/bin/alembic upgrade head
venv/bin/alembic downgrade -1
venv/bin/alembic upgrade head

# 5. PostgreSQL Integration Test
echo ""
echo "[5/5] Running PostgreSQL integration tests..."
DATABASE_URL=postgresql://partsops:partsops_test_password@localhost:5433/partsops_test \
venv/bin/python -m pytest tests/test_postgres_integration.py -v

echo ""
echo "=========================================="
echo "  ✅ All production checks passed!"
echo "=========================================="
