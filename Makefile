.PHONY: dev stop logs test test-fe install

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
	@echo "  make logs      — stream all logs"
	@echo "  make stop      — shut down"

stop:
	@if [ -f ".backend.pid" ]; then \
		kill $$(cat .backend.pid) 2>/dev/null || true; \
		rm .backend.pid; \
	fi
	@if [ -f ".frontend.pid" ]; then \
		kill $$(cat .frontend.pid) 2>/dev/null || true; \
		rm .frontend.pid; \
	fi
	@lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
	@lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true
	@echo "Stopped."

logs:
	@tail -f .backend.log .frontend.log

test:
	@.venv/bin/python -m pytest apps/api/ packages/ -q --tb=short

test-fe:
	@cd apps/web && npm test -- --passWithNoTests

install:
	@.venv/bin/pip install -r requirements.txt
