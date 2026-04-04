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

> **Choose your operating system below.** The macOS / Linux path is straightforward. The Windows path uses WSL 2 and has a few extra steps — follow it carefully.

---

### 🍎 macOS / Linux

#### 1. Clone and enter the repo

```bash
git clone <repo-url>
cd spendsmart-dashboard
```

#### 2. Set up environment variables

This project has **three** env files that need to be created and filled in. Copy each example file and edit it:

```bash
cp .env.example .env
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env.local
```

> 🔑 Get your Supabase values from your project dashboard at [supabase.com](https://supabase.com) → Project Settings → API.
> Get your Setu credentials from [fiu.setu.co](https://fiu.setu.co) (use sandbox credentials for local dev).

---

**`.env`** — Root backend config

| Variable | Required | Description |
|---|---|---|
| `SUPABASE_URL` | ✅ Required | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | ✅ Required | Supabase public anon key |
| `SUPABASE_SERVICE_KEY` | ✅ Required | Supabase service role key (keep secret) |
| `REDIS_URL` | ✅ Required | Leave as `redis://localhost:6379/0` for local dev |
| `ENVIRONMENT` | ✅ Required | Set to `development` for local dev |
| `LOG_LEVEL` | Optional | `INFO` by default |
| `TRANSFORMERS_OFFLINE` | Optional | Set to `1` after first run to skip HuggingFace network calls |
| `SENTRY_DSN` | Optional | Leave blank unless you have a Sentry project |
| `FLOWER_USER` / `FLOWER_PASSWORD` | Optional | Only needed if using the Flower monitoring dashboard |

---

**`apps/api/.env`** — API Gateway config (largely mirrors root `.env` but kept separate)

| Variable | Required | Description |
|---|---|---|
| `SUPABASE_URL` | ✅ Required | Same as root `.env` |
| `SUPABASE_ANON_KEY` | ✅ Required | Same as root `.env` |
| `SUPABASE_SERVICE_KEY` | ✅ Required | Same as root `.env` |
| `REDIS_URL` | ✅ Required | Leave as `redis://localhost:6379/0` |
| `SETU_CLIENT_ID` | ✅ Required | From your Setu FIU sandbox dashboard |
| `SETU_CLIENT_SECRET` | ✅ Required | From your Setu FIU sandbox dashboard |
| `ENVIRONMENT` | ✅ Required | `development` |
| `LOG_LEVEL` | Optional | `INFO` by default |
| `SENTRY_DSN` | Optional | Leave blank for local dev |

---

**`apps/web/.env.local`** — Next.js frontend config

| Variable | Required | Description |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | ✅ Required | Same Supabase URL as above |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | ✅ Required | Same anon key as above |
| `NEXT_PUBLIC_API_URL` | Optional | Leave as `http://localhost:8000/api/v1` for local dev |
| `NEXT_PUBLIC_SENTRY_DSN` | Optional | Leave blank for local dev |

#### 3. Create the Python virtual environment

```bash
python3 -m venv .venv
```

#### 4. Install all dependencies

```bash
make install
```

This installs Python packages from `requirements.txt` into `.venv` and runs `npm install` inside `apps/web/`.

#### 5. Start Redis

```bash
docker compose up redis -d
```

#### 6. Start the dev servers

```bash
make dev
```

This starts the FastAPI backend on **<http://localhost:8000>** and the Next.js frontend on **<http://localhost:3000>** as background processes. Logs stream to `.backend.log` and `.frontend.log`.

---

### 🪟 Windows (via WSL 2)

Windows is fully supported via **WSL 2** (Windows Subsystem for Linux). All commands below are run inside your WSL terminal, not PowerShell or CMD.

> **Before you start:** Make sure WSL 2 is installed with an Ubuntu distro. Open PowerShell and run `wsl --install` if you haven't already. Then open your Ubuntu terminal to continue.

#### 0. Open WSL and switch to root

Open PowerShell or Windows Terminal and enter WSL:

```powershell
wsl
```

Once inside WSL, switch to root so that all installation commands work without permission issues:

```bash
sudo su
# Enter your WSL user password when prompted
```

You should now see a prompt like `root@DESKTOP-XXXXX:/home/<you>/spendsmart-dashboard#`. Run all the steps below from this root shell.

> **Note:** Because you are running as root, files created during setup (`.env`, `.venv`, etc.) will be root-owned. Step 5 covers how to fix permissions so VSCode on Windows can edit them freely.

#### 1. Clone and enter the repo

Inside your WSL root shell:

```bash
git clone <repo-url>
cd spendsmart-dashboard
```

#### 2. Install Python 3.12 + venv

Ubuntu's default package list does not include `python3.12-venv`. You need to add the **deadsnakes PPA** first:

```bash
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install python3.12 python3.12-venv python3.12-dev -y
```

Verify the install:

```bash
python3.12 --version
# Expected: Python 3.12.x
```

#### 3. Create the Python virtual environment

> ⚠️ **Important:** Always create the venv *after* installing `python3.12-venv`. Creating it before will produce a broken venv with no `pip`.

```bash
python3.12 -m venv .venv
```

If you accidentally created a broken venv earlier, delete it first:

```bash
rm -rf .venv
python3.12 -m venv .venv
```

#### 4. Install Node.js 20

Node.js is not installed in WSL by default. Install it via the official NodeSource script:

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

Verify:

```bash
node --version   # Expected: v20.x.x
npm --version    # Expected: 10.x.x
```

#### 5. Set up environment variables

This project has **three** env files. Copy them all and fix permissions in one go:

```bash
cp .env.example .env
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env.local
chmod 666 .env apps/api/.env apps/web/.env.local
chown -R $USER:$USER /home/$USER/spendsmart-dashboard
```

> **Why chmod/chown:** Running as root in WSL means created files are root-owned. VSCode on Windows cannot save root-owned files without admin rights. This fixes that.

Now open each file in VSCode and fill in your values.

> 🔑 Get your Supabase values from [supabase.com](https://supabase.com) → Project Settings → API.
> Get your Setu credentials from [fiu.setu.co](https://fiu.setu.co) (use sandbox credentials for local dev).

---

**`.env`** — Root backend config

| Variable | Required | Description |
|---|---|---|
| `SUPABASE_URL` | ✅ Required | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | ✅ Required | Supabase public anon key |
| `SUPABASE_SERVICE_KEY` | ✅ Required | Supabase service role key (keep secret) |
| `REDIS_URL` | ✅ Required | Leave as `redis://localhost:6379/0` for local dev |
| `ENVIRONMENT` | ✅ Required | Set to `development` for local dev |
| `LOG_LEVEL` | Optional | `INFO` by default |
| `TRANSFORMERS_OFFLINE` | Optional | Set to `1` after first run to skip HuggingFace network calls |
| `SENTRY_DSN` | Optional | Leave blank unless you have a Sentry project |
| `FLOWER_USER` / `FLOWER_PASSWORD` | Optional | Only needed if using the Flower monitoring dashboard |

---

**`apps/api/.env`** — API Gateway config

| Variable | Required | Description |
|---|---|---|
| `SUPABASE_URL` | ✅ Required | Same as root `.env` |
| `SUPABASE_ANON_KEY` | ✅ Required | Same as root `.env` |
| `SUPABASE_SERVICE_KEY` | ✅ Required | Same as root `.env` |
| `REDIS_URL` | ✅ Required | Leave as `redis://localhost:6379/0` |
| `SETU_CLIENT_ID` | ✅ Required | From your Setu FIU sandbox dashboard |
| `SETU_CLIENT_SECRET` | ✅ Required | From your Setu FIU sandbox dashboard |
| `ENVIRONMENT` | ✅ Required | `development` |
| `LOG_LEVEL` | Optional | `INFO` by default |
| `SENTRY_DSN` | Optional | Leave blank for local dev |

---

**`apps/web/.env.local`** — Next.js frontend config

| Variable | Required | Description |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | ✅ Required | Same Supabase URL as above |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | ✅ Required | Same anon key as above |
| `NEXT_PUBLIC_API_URL` | Optional | Leave as `http://localhost:8000/api/v1` for local dev |
| `NEXT_PUBLIC_SENTRY_DSN` | Optional | Leave blank for local dev |

#### 6. Install all dependencies

```bash
make install
```

This runs `pip install -r requirements.txt` into `.venv` and `npm install` inside `apps/web/`. Both must succeed before continuing.

#### 7. Start Redis

Make sure Docker Desktop is installed and running on Windows with **WSL 2 integration enabled** (Docker Desktop → Settings → Resources → WSL Integration → enable for your Ubuntu distro).

Then start Redis:

```bash
docker compose up redis -d
```

Verify Redis is running:

```bash
docker compose ps
```

#### 8. Start the dev servers

```bash
make dev
```

This starts:
- **Backend** (FastAPI) → <http://localhost:8000>
- **Frontend** (Next.js) → <http://localhost:3000>

Logs are written to `.backend.log` and `.frontend.log`. Stream them with:

```bash
make logs
```

To stop everything:

```bash
make stop
```

---

#### Windows Troubleshooting

| Problem | Fix |
|---|---|
| `python3.12-venv` has no installation candidate | Add deadsnakes PPA: `sudo add-apt-repository ppa:deadsnakes/ppa -y && sudo apt update` |
| `make install` fails with `.venv/bin/pip not found` | Venv was created before installing `python3.12-venv`. Run `rm -rf .venv && python3.12 -m venv .venv` |
| `npm: not found` | Node.js not installed — follow Step 4 above |
| VSCode: "Insufficient permissions" when saving `.env` | Run `chmod 666 .env && chown -R $USER:$USER .` in WSL |
| Docker / Redis not starting | Ensure Docker Desktop is running and WSL 2 integration is enabled for your Ubuntu distro |

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
