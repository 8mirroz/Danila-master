#!/bin/bash
set -euo pipefail

echo "Starting Backend (FastAPI)..."
if [ -d "partsops-ai-manager/venv" ]; then
  source partsops-ai-manager/venv/bin/activate
  cd partsops-ai-manager
elif [ -d "venv" ]; then
  source venv/bin/activate
else
  echo "No venv found, using system python"
fi

export PARTSOPS_CORS_ORIGINS=${PARTSOPS_CORS_ORIGINS:-"http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:4173,http://127.0.0.1:4173,http://localhost:3000,http://127.0.0.1:3000"}

uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

echo "Starting Frontend (Vite)..."
cd 06_UI/admin_cockpit
npm install
npm run dev -- --port 5173 &
FRONTEND_PID=$!

echo "Both servers are running."
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:5173"

wait $BACKEND_PID $FRONTEND_PID

