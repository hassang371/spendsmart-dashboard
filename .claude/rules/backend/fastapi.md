---
paths:
  - "apps/api/**/*.py"
  - "apps/worker/**/*.py"
  - "packages/**/*.py"
---

# FastAPI / Python Rules (SCALE)

## Domain Module Structure

```
apps/api/domains/<domain>/
  router.py        ← FastAPI router, thin — delegates to service layer
  service.py       ← Business logic
  models.py        ← Pydantic models
  tests/
    test_<domain>.py
```

Core utilities in `apps/api/core/`:
- `rate_limiter.py` — rate limiting middleware
- `tasks/maintenance_tasks.py` — Celery periodic tasks

## Supabase Client Pattern

```python
# In route handlers — get client injected via dependency
from apps.api.core.supabase import get_supabase_client

async def my_endpoint(request: Request):
    supabase = get_supabase_client(request)
```

Do not instantiate the Supabase client directly inside handlers.

## Celery / Worker

- Tasks defined in `apps/worker/main.py`
- Always dispatch via `.delay()` or `.apply_async()` — never call task functions directly
- Worker logs go to `.worker.log` (gitignored)

## Testing

```bash
.venv/bin/python -m pytest apps/ packages/ -v        # all tests
.venv/bin/python -m pytest -k "test_name" -v         # specific test
```

- Test files go in `tests/` subdirectory of the domain being tested
- Use `pytest` fixtures — no `unittest.TestCase` classes
- Mock Supabase in unit tests — do not hit the real database

## Python Version

Python 3.14. Use modern syntax: `match` statements, `type X = ...` aliases, etc.
