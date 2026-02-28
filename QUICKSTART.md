# SCALE App - Quick Start Guide

## Prerequisites

- Docker Desktop installed and running
- Node.js & npm installed
- Git repo cloned

---

## Step 1: Start Backend (Terminal 1)

```bash
# Navigate to project root
cd /Users/hassangameryt/Documents/Antigravity/SCALE APP

# Start Docker services (API, Redis, Celery Workers, Flower)
./scripts/start-local.sh
```

**Wait for:** "✅ API is healthy" message

**Services started:**

- API: <http://localhost:8000>
- Flower: <http://localhost:5555>

---

## Step 2: Start Frontend (Terminal 2)

```bash
# Navigate to web app
cd /Users/hassangameryt/Documents/Antigravity/SCALE APP/apps/web

# Install dependencies (first time only)
npm install

# Start Next.js dev server
npm run dev
```

**Wait for:** "Ready on <http://localhost:3000>"

---

## Step 3: Open the App

Open browser: <http://localhost:3000>

---

## Verification Commands

```bash
# Check API health
curl http://localhost:8000/api/v1/health

# View API docs
curl http://localhost:8000/docs

# Check running containers
docker-compose ps

# View logs
docker-compose logs -f
```

---

## Stop Everything

```bash
# Stop backend
./scripts/stop-local.sh

# Stop frontend (in Terminal 2, press Ctrl+C)
```

---

## Troubleshooting

**Docker not running:**

```bash
open -a Docker
```

**Port already in use:**

```bash
# Kill processes on port 3000
lsof -ti:3000 | xargs kill -9

# Kill processes on port 8000
lsof -ti:8000 | xargs kill -9
```

**Rebuild Docker:**

```bash
./scripts/stop-local.sh
docker-compose build --no-cache
./scripts/start-local.sh
```
