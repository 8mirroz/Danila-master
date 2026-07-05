#!/bin/bash
echo "Starting Backend (FastAPI)..."
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo "Starting Frontend (Vite)..."
cd 06_UI/admin_cockpit
npm run dev -- --port 3000 &
FRONTEND_PID=$!

echo "Both servers are running."
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:3000"

wait $BACKEND_PID
wait $FRONTEND_PID
