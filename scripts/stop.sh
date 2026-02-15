#!/bin/bash
set -e

# Colors
RED='\033[0;31m'
NC='\033[0m'

echo -e "${RED}Stopping SCALE App Services...${NC}"

# Stop Frontend (Next.js typically on 3000)
lsof -ti:3000 | xargs kill 2>/dev/null || echo "Frontend (3000) already stopped."

# Stop API (Uvicorn typically on 8000)
lsof -ti:8000 | xargs kill 2>/dev/null || echo "API Gateway (8000) already stopped."

# Stop Worker (Python Process)
pkill -f "apps.worker.main" || echo "Worker already stopped."

echo -e "${RED}All services stopped.${NC}"
