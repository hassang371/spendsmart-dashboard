#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Starting SCALE App Development Environment...${NC}"

# Ensure we are in the project root
cd "$(dirname "$0")/.."

# Activate Virtual Environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Virtual environment not found. Please run 'python -m venv .venv' first."
    exit 1
fi

# Function to kill processes on exit
cleanup() {
    echo -e "\n${BLUE}Shutting down services...${NC}"
    kill $API_PID $WORKER_PID $FRONTEND_PID 2>/dev/null
    exit
}

trap cleanup SIGINT SIGTERM

# 1. Start API Gateway
echo -e "${GREEN}🚀 Starting API Gateway (Port 8000)...${NC}"
uvicorn apps.api.main:app --reload --port 8000 &
API_PID=$!

# 2. Start AI Worker
echo -e "${GREEN}🧠 Starting AI Worker...${NC}"
python -m apps.worker.main &
WORKER_PID=$!

# 3. Start Frontend
echo -e "${GREEN}💻 Starting Frontend (Port 3000)...${NC}"
cd apps/web
npm run dev &
FRONTEND_PID=$!

# Wait for all background processes
wait
