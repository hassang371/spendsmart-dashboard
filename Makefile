.PHONY: dev worker stop logs clean-logs test test-fe install

dev:
	@echo "Starting SCALE App..."
	@$(MAKE) -s stop
	@if [ ! -d ".venv" ]; then echo "Error: .venv not found. Run 'make install'."; exit 1; fi
	@.venv/bin/python3 -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload > .backend.log 2>&1 & echo $$! > .backend.pid
	@(cd apps/web && npm run dev) > .frontend.log 2>&1 & echo $$! > .frontend.pid
	@echo ""
	@echo "  Frontend: http://localhost:3000"
	@echo "  Backend:  http://localhost:8000"
	@echo ""
	@echo "  make worker     — start background job worker"
	@echo "  make logs       — stream all logs"
	@echo "  make stop       — shut down everything"

worker:
	@echo "Starting SCALE worker..."
	@if [ ! -d ".venv" ]; then echo "Error: .venv not found. Run 'make install'."; exit 1; fi
	@PYTHONPATH=. .venv/bin/python3 apps/worker/main.py > .worker.log 2>&1 & echo $$! > .worker.pid
	@echo "  Worker PID: $$(cat .worker.pid) — logs: .worker.log"

stop:
	@if [ -f ".backend.pid" ]; then \
		kill $$(cat .backend.pid) 2>/dev/null || true; \
		rm -f .backend.pid; \
	fi
	@if [ -f ".frontend.pid" ]; then \
		kill $$(cat .frontend.pid) 2>/dev/null || true; \
		rm -f .frontend.pid; \
	fi
	@if [ -f ".worker.pid" ]; then \
		kill $$(cat .worker.pid) 2>/dev/null || true; \
		rm -f .worker.pid; \
	fi
	@lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
	@lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true
	@echo "Stopped."

clean-logs:
	@rm -f .backend.log .frontend.log .worker.log
	@echo "Logs cleared."

logs:
	@tail -f .backend.log .frontend.log .worker.log 2>/dev/null || tail -f .backend.log .frontend.log

test:
	@.venv/bin/python -m pytest apps/ packages/ -q --tb=short

test-fe:
	@cd apps/web && npm test -- --passWithNoTests

check:
	@echo "Running all checks..."
	@cd apps/web && npm run lint
	@cd apps/web && npx tsc --noEmit
	@.venv/bin/python -m pytest apps/ packages/ -q --tb=short
	@echo "All checks passed."

install:
	@.venv/bin/pip install -r requirements.txt
	@cd apps/web && npm install
