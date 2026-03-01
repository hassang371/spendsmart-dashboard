#!/bin/bash
set -euo pipefail

echo "==================================="
echo " Starting SCALE App locally"
echo "==================================="

# Call stop.sh to clean up any existing instances first
if [ -f "stop.sh" ]; then
    ./stop.sh
fi

# 1. Start backend securely
echo "--> Starting Python API (FastAPI)..."
if [ -d ".venv" ]; then
    .venv/bin/python3 -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload &
    BACKEND_PID=$!
    echo $BACKEND_PID > .backend.pid
else
    echo "Error: Virtual environment (.venv) not found. Cannot start backend."
fi

# 2. Start frontend 
echo "--> Starting Next.js Web App..."
if [ -d "apps/web" ]; then
    cd apps/web
    npm run dev &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > ../.frontend.pid
    cd ../..
else
    echo "Error: apps/web directory not found."
fi

echo "==================================="
echo " SCALE App is now running!"
echo " Frontend: http://localhost:3000"
echo " Backend:  http://localhost:8000"
echo "==================================="
echo ""
echo "To stop the app, run: ./stop.sh"
