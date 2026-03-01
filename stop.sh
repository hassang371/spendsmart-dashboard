#!/bin/bash

echo "==================================="
echo " Stopping SCALE App"
echo "==================================="

if [ -f ".backend.pid" ]; then
    PID=$(cat .backend.pid)
    echo "--> Stopping FastAPI backend (PID: $PID)..."
    kill $PID 2>/dev/null || true
    rm .backend.pid
else
    echo "--> Stopping FastAPI (by port 8000)..."
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
fi

if [ -f ".frontend.pid" ]; then
    PID=$(cat .frontend.pid)
    echo "--> Stopping Next.js frontend (PID: $PID)..."
    kill $PID 2>/dev/null || true
    rm .frontend.pid
else
    echo "--> Stopping Next.js (by port 3000)..."
    lsof -ti:3000 | xargs kill -9 2>/dev/null || true
fi

# Fallback kill for node/python processes just in case
lsof -ti:3000 | xargs kill -9 2>/dev/null || true
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

echo "==================================="
echo " All services stopped successfully!"
echo "==================================="
