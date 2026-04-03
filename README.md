# SCALE — AI-Powered Personal Finance

SCALE (SpendSmart) is an AI-powered personal finance platform. It connects to your bank accounts via the Setu Account Aggregator, automatically categorises transactions using a per-user fine-tuned MiniLM model, detects spending anomalies, forecasts future cash flow, and surfaces insights through an analytics dashboard.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS |
| Backend | FastAPI, Python 3.11+, Celery |
| Database | Supabase (Postgres + Auth + Storage) |
| Cache / Queue | Redis |
| ML / AI | MiniLM v2 (categorisation), TFT (forecasting), Modal (training) |
| Frontend Hosting | Vercel |
| Backend Hosting | Railway |
| Error Tracking | Sentry |

---

## Prerequisites

Before setting up, make sure you have:

- **Python 3.11+** — `python3 --version`
- **Node.js 20+** — `node --version`
- **Docker** — for running Redis locally (or install Redis natively)
- **A Supabase project** — [supabase.com](https://supabase.com), free tier is fine

---

## Local Setup

### 1. Clone and enter the repo

```bash
git clone <repo-url>
cd "SCALE APP"
```

### 2. Set up environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in:

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=<your anon key>
SUPABASE_SERVICE_KEY=<your service key>
REDIS_URL=redis://localhost:6379/0
```

Then create the frontend env file:

```bash
# apps/web/.env.local
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<your anon key>
```

### 3. Create the Python virtual environment

```bash
python3 -m venv .venv
```

### 4. Install all dependencies

```bash
make install
```

This installs Python packages from `requirements.txt` into `.venv` and runs `npm install` inside `apps/web/`.

### 5. Start Redis

```bash
docker compose up redis -d
```

### 6. Start the dev servers

```bash
make dev
```

This starts the FastAPI backend on **<http://localhost:8000>** and the Next.js frontend on **<http://localhost:3000>** as background processes. Logs stream to `.backend.log` and `.frontend.log`.

---

## ML / AI Focus Setup

> If you are working primarily on the ML/AI side (packages, training pipeline, categorisation), you can skip the frontend entirely.

```bash
# 1. Create venv and install Python deps only
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Start Redis and the backend only
docker compose up redis -d
.venv/bin/python -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload

# 3. Run all Python tests
make test

# 4. Run tests for a specific package
.venv/bin/python -m pytest packages/categorization/ -q
.venv/bin/python -m pytest packages/forecasting/ -q
.venv/bin/python -m pytest packages/ingestion_engine/ -q
```

The three ML packages (`packages/categorization/`, `packages/forecasting/`, `packages/ingestion_engine/`) are pure Python and have no frontend dependency. You can develop and test them standalone.

On first run the HuggingFace MiniLM model will be downloaded (~90MB). Set `TRANSFORMERS_OFFLINE=1` in `.env` after that to prevent unnecessary network calls.

---

## Dev Commands

| Command | What it does |
|---|---|
| `make dev` | Start frontend (:3000) + backend (:8000) |
| `make worker` | Start the Celery background worker |
| `make stop` | Kill all running servers |
| `make logs` | Tail all log files |
| `make test` | Run all Python tests (apps/ + packages/) |
| `make test-fe` | Run frontend tests (vitest) |
| `make check` | Full DoD check — lint + tsc + pytest |
| `make install` | Install all dependencies |
| `make clean-logs` | Delete .backend.log / .frontend.log / .worker.log |
| `cd apps/web && npm run lint` | ESLint |
| `cd apps/web && npm run build` | Next.js production build |
| `.venv/bin/python -m pytest -k "test_name"` | Run a specific test |
| `npx tsc --noEmit` | TypeScript type check |

---

## Project Structure

```
SCALE APP/
├── apps/
│   ├── api/          # FastAPI backend — domains, core, routers, tasks
│   ├── web/          # Next.js frontend — app router, components, lib
│   └── worker/       # Celery async worker
├── packages/
│   ├── categorization/     # MiniLM transaction classifier
│   ├── forecasting/        # TFT cash flow forecasting model
│   └── ingestion_engine/   # CSV/Excel bank statement parser
├── supabase/
│   └── migrations/         # SQL migration history
├── docs/                   # All project documentation
├── scripts/                # Utility and maintenance scripts
├── architecture/           # Schema references and migration notes
├── docker-compose.yml      # Redis + API + Worker + Flower (monitoring)
├── Makefile                # Dev commands
├── pyproject.toml          # Python project config + linting rules
├── requirements.txt        # Python dependencies
└── .env.example            # Environment variable template
```

---

## Key Documentation

| Doc | Purpose |
|---|---|
| [`docs/design/codebase-reference.md`](docs/design/codebase-reference.md) | Every file and directory explained in detail |
| [`docs/design/ai-tooling-guide.md`](docs/design/ai-tooling-guide.md) | Guide to the AI development tooling layer |
| [`docs/design/system-architecture.md`](docs/design/system-architecture.md) | System architecture HLD |
| [`docs/design/api-design.md`](docs/design/api-design.md) | API design HLD |
| [`docs/design/database-design.md`](docs/design/database-design.md) | Database schema HLD |
| [`docs/STANDARDS.md`](docs/STANDARDS.md) | Documentation standards for all agents and humans |

---

## AI Development Tooling

This project is developed with Claude Code (Anthropic's AI coding CLI). The development workflow is governed by rules in `.claude/CLAUDE.md` — covering docs-driven development, TDD, commit conventions, and documentation gates.

If you are using Claude Code on this project, read `.claude/CLAUDE.md` first. It defines how work is done here.
