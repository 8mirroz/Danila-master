#!/bin/bash
set -euo pipefail

echo "======================================================="
echo "   Starting PartsOps AI Manager Control Plane v3       "
echo "======================================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

# Run one-time hermes setup
if [ -f "scripts/setup_hermes.sh" ]; then
  bash scripts/setup_hermes.sh || true
fi

# Load Hermes API Key secret
if [ -f ".hermes_api_key" ]; then
  export HERMES_API_KEY=$(cat .hermes_api_key)
  export API_SERVER_KEY="${HERMES_API_KEY}"
fi

# Load .env
if [ -f ".env" ]; then
  set -a
  source .env
  set +a
fi

if [ -z "${HERMES_API_KEY:-}" ] || [ "${#HERMES_API_KEY}" -lt 16 ] || [ "${HERMES_API_KEY}" = "partsops-hermes-secret-key" ]; then
  echo "[!] HERMES_API_KEY must be a strong secret (at least 16 characters)."
  exit 1
fi
export API_SERVER_KEY="${HERMES_API_KEY}"

# Trap SIGINT/SIGTERM to kill only spawned child processes
cleanup() {
  echo ""
  echo "Shutting down child processes..."
  if [ -n "${PIPELINE_WORKER_PID:-}" ] && kill -0 "${PIPELINE_WORKER_PID}" 2>/dev/null; then
    echo "Stopping Pipeline Worker (PID ${PIPELINE_WORKER_PID})..."
    kill "${PIPELINE_WORKER_PID}" 2>/dev/null || true
  fi
  if [ -n "${HERMES_PID:-}" ] && kill -0 "${HERMES_PID}" 2>/dev/null; then
    echo "Stopping Hermes Sidecar (PID ${HERMES_PID})..."
    kill "${HERMES_PID}" 2>/dev/null || true
  fi
  if [ -n "${BACKEND_PID:-}" ] && kill -0 "${BACKEND_PID}" 2>/dev/null; then
    echo "Stopping Backend (PID ${BACKEND_PID})..."
    kill "${BACKEND_PID}" 2>/dev/null || true
  fi
  if [ -n "${FRONTEND_PID:-}" ] && kill -0 "${FRONTEND_PID}" 2>/dev/null; then
    echo "Stopping Frontend (PID ${FRONTEND_PID})..."
    kill "${FRONTEND_PID}" 2>/dev/null || true
  fi
  exit 0
}
trap cleanup SIGINT SIGTERM EXIT
PIPELINE_WORKER_PID=""

# 1. Start Hermes native API Server through the gateway platform (Port 8642)
echo "Starting Hermes native API Server (127.0.0.1:8642)..."
if command -v hermes &> /dev/null; then
  API_SERVER_ENABLED=1 \
  API_SERVER_PORT=8642 \
  API_SERVER_HOST=127.0.0.1 \
  hermes --profile partsops gateway run --force --no-supervise &
  HERMES_PID=$!
else
  echo "[!] Hermes CLI binary not found. Native Copilot cannot start."
  exit 1
fi

# Wait bounded up to 20s for Hermes readiness if spawned
if [ -n "${HERMES_PID}" ]; then
  echo "Waiting for authenticated Hermes capabilities (max 20s)..."
  WAIT_COUNTER=0
  until curl -fsS -H "Authorization: Bearer ${HERMES_API_KEY}" http://127.0.0.1:8642/v1/capabilities > /dev/null || [ ${WAIT_COUNTER} -ge 20 ]; do
    sleep 1
    WAIT_COUNTER=$((WAIT_COUNTER + 1))
  done

  if [ ${WAIT_COUNTER} -lt 20 ]; then
    echo "[✓] Hermes API Gateway is ready on http://127.0.0.1:8642/v1/capabilities"
  else
    echo "[!] Hermes API Gateway did not become ready within 20s. Aborting startup."
    exit 1
  fi
fi

# 2. Start Backend (FastAPI - Port 8000)
echo "Starting Backend (FastAPI)..."
if [ -d "venv" ]; then
  source venv/bin/activate
elif [ -d "partsops-ai-manager/venv" ]; then
  source partsops-ai-manager/venv/bin/activate
fi

export PARTSOPS_CORS_ORIGINS=${PARTSOPS_CORS_ORIGINS:-"http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:4173,http://127.0.0.1:4173,http://localhost:3000,http://127.0.0.1:3000"}
export PYTHONPATH="${SCRIPT_DIR}${PYTHONPATH:+:$PYTHONPATH}"

uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# 2b. Optional durable pipeline worker (Kanban queue consumers)
if [ "${PARTSOPS_START_PIPELINE_WORKER:-0}" = "1" ]; then
  echo "Starting Pipeline Worker (PARTSOPS_START_PIPELINE_WORKER=1)..."
  python -m app.automation.pipeline_worker --poll-seconds "${PARTSOPS_PIPELINE_POLL_SECONDS:-1}" &
  PIPELINE_WORKER_PID=$!
else
  echo "[i] Pipeline worker not started (set PARTSOPS_START_PIPELINE_WORKER=1 to enable)."
  echo "    Queued pipeline runs stay in 'queued' until a worker claims them."
fi

# 3. Start Frontend (Vite - Port 5173)
echo "Starting Frontend (Vite)..."
if [ -d "06_UI/admin_cockpit" ]; then
  cd 06_UI/admin_cockpit
  npm run dev -- --port 5173 &
  FRONTEND_PID=$!
  cd ../..
fi

echo "======================================================="
echo " All services running:"
echo " Backend:  http://localhost:8000"
echo " Frontend: http://localhost:5173"
echo " Hermes:   http://127.0.0.1:8642 (Internal)"
if [ -n "${PIPELINE_WORKER_PID}" ]; then
  echo " Worker:   pipeline_worker PID ${PIPELINE_WORKER_PID}"
fi
echo "======================================================="

if [ -n "${PIPELINE_WORKER_PID}" ]; then
  wait ${BACKEND_PID} ${FRONTEND_PID} ${PIPELINE_WORKER_PID}
else
  wait ${BACKEND_PID} ${FRONTEND_PID}
fi
