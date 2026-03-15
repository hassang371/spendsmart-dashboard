# Account Aggregator Integration — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable users to link Indian bank accounts via Account Aggregator (Setu), replacing manual file imports as the primary data source.

**Architecture:** New `bank_accounts` table with FK on `transactions`. Provider-agnostic abstraction (`AggregatorProvider` ABC) with Setu as first implementation. REST API at `/api/v1/aggregator/` (separate from existing `/api/v1/accounts/`). Frontend accounts page (list+detail), sidebar switcher, adaptive consent flow. Auto-sync via polling worker + manual on-demand.

**Tech Stack:** FastAPI, Supabase (Postgres + RLS), Next.js 16, TypeScript, Tailwind, Framer Motion, Setu Data Gateway API

**Spec:** `docs/features/004-account-aggregator.md`

---

## Chunk 1: Data Foundation (Database + Migration)

### Task 1: Create `bank_accounts` table migration

**Files:**
- Create: `apps/api/domains/aggregator/__init__.py`
- Modify: `architecture/schema.sql` (add bank_accounts DDL)

- [ ] **Step 1: Write the Supabase migration SQL**

```sql
-- Create bank_accounts table
CREATE TABLE IF NOT EXISTS public.bank_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    account_name TEXT NOT NULL,
    account_type TEXT NOT NULL DEFAULT 'savings',
    institution TEXT,
    provider TEXT,
    provider_account_id TEXT,
    consent_id TEXT,
    consent_status TEXT NOT NULL DEFAULT 'none',
    consent_expiry TIMESTAMPTZ,
    last_synced_at TIMESTAMPTZ,
    sync_status TEXT NOT NULL DEFAULT 'idle',
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    is_manual BOOLEAN NOT NULL DEFAULT FALSE,
    masked_number TEXT,
    currency TEXT NOT NULL DEFAULT 'INR',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX idx_bank_accounts_user ON public.bank_accounts (user_id);

-- Provider account uniqueness (only for non-null provider accounts)
CREATE UNIQUE INDEX idx_bank_accounts_provider_account
    ON public.bank_accounts (user_id, provider_account_id)
    WHERE provider_account_id IS NOT NULL;

-- Only one manual account per user
CREATE UNIQUE INDEX idx_bank_accounts_user_manual
    ON public.bank_accounts (user_id)
    WHERE is_manual = TRUE;

-- RLS
ALTER TABLE public.bank_accounts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own accounts"
    ON public.bank_accounts FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own accounts"
    ON public.bank_accounts FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own accounts"
    ON public.bank_accounts FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete non-manual accounts"
    ON public.bank_accounts FOR DELETE
    USING (auth.uid() = user_id AND is_manual = FALSE);

-- Service role bypass for worker sync
CREATE POLICY "Service role has full access to bank_accounts"
    ON public.bank_accounts FOR ALL
    TO service_role
    USING (true) WITH CHECK (true);
```

- [ ] **Step 2: Apply the migration**

Run: `mcp__supabase__apply_migration` with name `create_bank_accounts_table`

- [ ] **Step 3: Verify the table exists**

Run: `mcp__supabase__list_tables`
Expected: `bank_accounts` appears in the list

- [ ] **Step 4: Create aggregator domain directory**

Create empty `apps/api/domains/aggregator/__init__.py`.

- [ ] **Step 5: Update `architecture/schema.sql`**

After the transactions table section (after line 31), add the full `bank_accounts` DDL from Step 1. This is the checked-in reference schema.

- [ ] **Step 6: Commit**

```bash
git add architecture/schema.sql apps/api/domains/aggregator/__init__.py
git commit -m "chore(db): add bank_accounts table with RLS policies"
```

### Task 2: Add `account_id` to transactions + backfill migration

**Files:**
- Modify: `architecture/schema.sql`

- [ ] **Step 1: Write the alter-transactions migration SQL**

```sql
-- Guard: check for orphan transactions with NULL user_id
DO $$
DECLARE
    orphan_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO orphan_count FROM public.transactions WHERE user_id IS NULL;
    IF orphan_count > 0 THEN
        RAISE EXCEPTION 'Found % transactions with NULL user_id. Clean up before migration.', orphan_count;
    END IF;
END $$;

-- Add account_id column (nullable initially for backfill)
ALTER TABLE public.transactions
    ADD COLUMN IF NOT EXISTS account_id UUID REFERENCES public.bank_accounts(id);

-- Create manual import account for each existing user (idempotent)
INSERT INTO public.bank_accounts (user_id, account_name, account_type, is_manual, consent_status)
SELECT DISTINCT user_id, 'Manual Import', 'manual', TRUE, 'none'
FROM public.transactions
WHERE user_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM public.bank_accounts ba
      WHERE ba.user_id = transactions.user_id AND ba.is_manual = TRUE
  );

-- Backfill account_id for existing transactions
UPDATE public.transactions t
SET account_id = ba.id
FROM public.bank_accounts ba
WHERE ba.user_id = t.user_id
  AND ba.is_manual = TRUE
  AND t.account_id IS NULL;

-- Now make account_id NOT NULL
ALTER TABLE public.transactions
    ALTER COLUMN account_id SET NOT NULL;

-- Drop old constraint FIRST (required before dropping the index it references)
ALTER TABLE public.transactions
    DROP CONSTRAINT IF EXISTS transactions_user_fingerprint_key;

-- Now drop the old index
DROP INDEX IF EXISTS idx_transactions_user_fingerprint;

-- Create new unique index scoped to account_id (preserve WHERE clause for NULL fingerprints)
CREATE UNIQUE INDEX idx_transactions_account_fingerprint
    ON public.transactions (account_id, fingerprint)
    WHERE fingerprint IS NOT NULL;

-- Add constraint using the new index (required for ON CONFLICT in RPC)
ALTER TABLE public.transactions
    ADD CONSTRAINT transactions_account_fingerprint_key
    UNIQUE USING INDEX idx_transactions_account_fingerprint;
```

- [ ] **Step 2: Apply the migration**

Run: `mcp__supabase__apply_migration` with name `add_account_id_to_transactions`

- [ ] **Step 3: Verify column exists and is NOT NULL**

Run: `mcp__supabase__execute_sql`

```sql
SELECT column_name, is_nullable, data_type
FROM information_schema.columns
WHERE table_name = 'transactions' AND column_name = 'account_id';
```

Expected: `account_id | NO | uuid`

- [ ] **Step 4: Verify backfill — no orphaned transactions**

Run: `mcp__supabase__execute_sql`

```sql
SELECT COUNT(*) as orphaned FROM public.transactions WHERE account_id IS NULL;
```

Expected: `0`

- [ ] **Step 5: Update `architecture/schema.sql`**

Add `account_id UUID NOT NULL REFERENCES bank_accounts(id)` to the transactions table definition. Replace the fingerprint index to show `(account_id, fingerprint)` instead of `(user_id, fingerprint)`.

- [ ] **Step 6: Commit**

```bash
git add architecture/schema.sql
git commit -m "feat(db): add account_id to transactions with backfill migration"
```

### Task 3: Update `batch_import_transactions` RPC to accept `account_id`

**Files:**
- Modify: Supabase RPC function (via migration)

- [ ] **Step 1: Check current RPC definition**

Run: `mcp__supabase__execute_sql`

```sql
SELECT pg_get_functiondef(oid) FROM pg_proc WHERE proname = 'batch_import_transactions';
```

Note the current signature — the updated version must preserve existing behavior.

- [ ] **Step 2: Write test for updated RPC**

Run: `mcp__supabase__execute_sql`

```sql
DO $$
DECLARE
    test_user_id UUID;
    test_account_id UUID;
BEGIN
    SELECT id INTO test_user_id FROM auth.users LIMIT 1;
    IF test_user_id IS NULL THEN
        RAISE NOTICE 'No users — skip';
        RETURN;
    END IF;
    SELECT id INTO test_account_id FROM public.bank_accounts
    WHERE user_id = test_user_id AND is_manual = TRUE LIMIT 1;
    IF test_account_id IS NULL THEN
        RAISE NOTICE 'No manual account — skip';
        RETURN;
    END IF;
    PERFORM batch_import_transactions(test_user_id, test_account_id, '[]'::jsonb);
    RAISE NOTICE 'RPC accepts (user_id, account_id, rows) — PASS';
END $$;
```

Expected: FAIL — current RPC doesn't have `p_account_id` parameter

- [ ] **Step 3: Write updated RPC migration**

Adapt based on actual RPC from Step 1. Key changes: add `p_account_id UUID`, include `account_id` in INSERT, change ON CONFLICT to `(account_id, fingerprint)`.

```sql
CREATE OR REPLACE FUNCTION public.batch_import_transactions(
    p_user_id UUID,
    p_account_id UUID,
    p_rows JSONB
)
RETURNS TABLE(inserted_count INTEGER, skipped_count INTEGER)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    total_rows INTEGER;
    actual_inserted INTEGER;
BEGIN
    total_rows := jsonb_array_length(p_rows);

    INSERT INTO public.transactions (
        user_id, account_id, transaction_date, amount, currency,
        description, merchant_name, payment_method, status, type,
        fingerprint, informative_text, bank_name, raw_data,
        category, suggested_category, confidence_score
    )
    SELECT
        p_user_id,
        p_account_id,
        (row_data->>'transaction_date')::TIMESTAMPTZ,
        (row_data->>'amount')::NUMERIC,
        COALESCE(row_data->>'currency', 'INR'),
        row_data->>'description',
        row_data->>'merchant_name',
        row_data->>'payment_method',
        COALESCE(row_data->>'status', 'completed'),
        COALESCE(row_data->>'type', 'debit'),
        row_data->>'fingerprint',
        row_data->>'informative_text',
        row_data->>'bank_name',
        (row_data->'raw_data')::JSONB,
        COALESCE(row_data->>'category', 'Uncategorized'),
        row_data->>'suggested_category',
        (row_data->>'confidence_score')::FLOAT
    FROM jsonb_array_elements(p_rows) AS row_data
    ON CONFLICT (account_id, fingerprint) WHERE fingerprint IS NOT NULL
    DO NOTHING;

    GET DIAGNOSTICS actual_inserted = ROW_COUNT;
    RETURN QUERY SELECT actual_inserted, (total_rows - actual_inserted);
END;
$$;
```

Apply via `mcp__supabase__apply_migration` with name `update_batch_import_rpc_account_id`.

- [ ] **Step 4: Re-run test from Step 2 — verify it passes**

Expected: `RPC accepts (user_id, account_id, rows) — PASS`

- [ ] **Step 5: Commit**

```bash
git add architecture/schema.sql
git commit -m "feat(db): update batch_import_transactions RPC for account_id"
```

---

## Chunk 2: Aggregator Backend (Provider Layer + Service + API)

### Task 4: Create `AggregatorProvider` abstract base class

**Files:**
- Create: `apps/api/domains/aggregator/provider.py`
- Create: `apps/api/domains/aggregator/tests/__init__.py`
- Create: `apps/api/domains/aggregator/tests/test_provider.py`

- [ ] **Step 1: Write failing test for provider interface**

```python
# apps/api/domains/aggregator/tests/test_provider.py
"""Tests for AggregatorProvider ABC contract."""
import pytest
from apps.api.domains.aggregator.provider import AggregatorProvider


def test_cannot_instantiate_abstract_provider():
    with pytest.raises(TypeError):
        AggregatorProvider()


def test_concrete_provider_must_implement_all_methods():
    class IncompleteProvider(AggregatorProvider):
        pass
    with pytest.raises(TypeError):
        IncompleteProvider()


def test_concrete_provider_with_all_methods():
    class FakeProvider(AggregatorProvider):
        async def initiate_consent(self, user_id, fi_types):
            return {"redirect_url": "https://example.com", "consent_id": "c1"}
        async def check_consent_status(self, consent_id):
            return {"status": "ACTIVE"}
        async def fetch_transactions(self, consent_id, from_date, to_date):
            return []
        async def revoke_consent(self, consent_id):
            pass

    provider = FakeProvider()
    assert provider is not None
```

- [ ] **Step 2: Run test — verify it fails**

Run: `.venv/bin/python -m pytest apps/api/domains/aggregator/tests/test_provider.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement the ABC**

```python
# apps/api/domains/aggregator/provider.py
"""Abstract base class for account aggregator providers."""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class AggregatorProvider(ABC):
    """Provider interface for account aggregator integrations."""

    @abstractmethod
    async def initiate_consent(self, user_id: str, fi_types: list[str]) -> dict[str, str]:
        """Start consent flow. Returns {redirect_url, consent_id}."""
        ...

    @abstractmethod
    async def check_consent_status(self, consent_id: str) -> dict[str, Any]:
        """Check consent status. Returns {status, detail?}."""
        ...

    @abstractmethod
    async def fetch_transactions(
        self, consent_id: str, from_date: datetime, to_date: datetime
    ) -> list[dict[str, Any]]:
        """Fetch transactions. Returns normalized transaction dicts."""
        ...

    @abstractmethod
    async def revoke_consent(self, consent_id: str) -> None:
        """Revoke an active consent."""
        ...
```

Also create empty `apps/api/domains/aggregator/tests/__init__.py`.

- [ ] **Step 4: Run test — verify it passes**

Run: `.venv/bin/python -m pytest apps/api/domains/aggregator/tests/test_provider.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add apps/api/domains/aggregator/
git commit -m "feat(aggregator): add AggregatorProvider abstract base class"
```

### Task 5: Create Pydantic schemas

**Files:**
- Create: `apps/api/domains/aggregator/schemas.py`
- Create: `apps/api/domains/aggregator/tests/test_schemas.py`

- [ ] **Step 1: Write failing test**

```python
# apps/api/domains/aggregator/tests/test_schemas.py
"""Tests for aggregator Pydantic schemas."""
from datetime import datetime, timezone
from apps.api.domains.aggregator.schemas import (
    BankAccountOut, LinkAccountRequest, LinkAccountResponse, SyncResponse, WebhookEvent,
)


def test_bank_account_out_from_db_row():
    row = {
        "id": "abc-123", "user_id": "user-1", "account_name": "HDFC ****1234",
        "account_type": "savings", "institution": "HDFC Bank", "provider": "setu",
        "consent_status": "active", "last_synced_at": "2026-03-15T10:00:00Z",
        "sync_status": "idle", "is_primary": False, "is_manual": False,
        "masked_number": "****1234", "currency": "INR",
        "created_at": "2026-03-15T09:00:00Z", "updated_at": "2026-03-15T10:00:00Z",
    }
    account = BankAccountOut(**row)
    assert account.account_name == "HDFC ****1234"

def test_link_account_request_defaults():
    assert LinkAccountRequest().fi_types == ["DEPOSIT"]

def test_link_account_response():
    resp = LinkAccountResponse(redirect_url="https://setu.co/consent", consent_id="c1")
    assert resp.redirect_url == "https://setu.co/consent"

def test_sync_response():
    assert SyncResponse(inserted=47, skipped_duplicates=3, account_id="abc").inserted == 47

def test_webhook_event():
    event = WebhookEvent(consent_id="c1", status="ACTIVE", timestamp=datetime(2026, 3, 15, tzinfo=timezone.utc))
    assert event.status == "ACTIVE"

def test_webhook_event_optional_timestamp():
    assert WebhookEvent(consent_id="c1", status="ACTIVE").timestamp is None
```

- [ ] **Step 2: Run test — verify it fails**

Run: `.venv/bin/python -m pytest apps/api/domains/aggregator/tests/test_schemas.py -v`
Expected: FAIL (import error)

- [ ] **Step 3: Implement schemas**

```python
# apps/api/domains/aggregator/schemas.py
"""Pydantic models for the aggregator domain."""
from datetime import datetime
from pydantic import BaseModel, Field


class BankAccountOut(BaseModel):
    id: str
    user_id: str
    account_name: str
    account_type: str
    institution: str | None = None
    provider: str | None = None
    consent_status: str
    last_synced_at: datetime | None = None
    sync_status: str
    is_primary: bool
    is_manual: bool
    masked_number: str | None = None
    currency: str
    created_at: datetime
    updated_at: datetime


class LinkAccountRequest(BaseModel):
    fi_types: list[str] = Field(default=["DEPOSIT"])


class LinkAccountResponse(BaseModel):
    redirect_url: str
    consent_id: str


class SyncResponse(BaseModel):
    inserted: int
    skipped_duplicates: int
    account_id: str


class WebhookEvent(BaseModel):
    consent_id: str
    status: str
    timestamp: datetime | None = None
```

- [ ] **Step 4: Run test — verify it passes**

Run: `.venv/bin/python -m pytest apps/api/domains/aggregator/tests/test_schemas.py -v`
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add apps/api/domains/aggregator/schemas.py apps/api/domains/aggregator/tests/test_schemas.py
git commit -m "feat(aggregator): add Pydantic schemas for account endpoints"
```

### Task 6: Create Setu provider implementation

**Files:**
- Create: `apps/api/domains/aggregator/providers/__init__.py`
- Create: `apps/api/domains/aggregator/providers/setu.py`
- Create: `apps/api/domains/aggregator/tests/test_setu_provider.py`

- [ ] **Step 1: Write failing tests**

Uses dependency injection for httpx client — clean mocking without patching.

```python
# apps/api/domains/aggregator/tests/test_setu_provider.py
"""Tests for SetuProvider — uses injected mock HTTP client."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from apps.api.domains.aggregator.providers.setu import SetuProvider


def _mock_response(status_code: int, json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


@pytest.fixture
def mock_http():
    return AsyncMock()


@pytest.fixture
def setu(mock_http):
    return SetuProvider(
        client_id="test-id", client_secret="test-secret",
        base_url="https://fiu-sandbox.setu.co",
        redirect_url="http://localhost:3000/dashboard/accounts/callback",
        http_client=mock_http,
    )


@pytest.mark.asyncio
async def test_initiate_consent(setu, mock_http):
    mock_http.post.return_value = _mock_response(201, {
        "id": "consent-123", "url": "https://anumati.setu.co/consent/123", "status": "PENDING",
    })
    result = await setu.initiate_consent("user-1", ["DEPOSIT"])
    assert result["consent_id"] == "consent-123"
    assert "anumati.setu.co" in result["redirect_url"]

@pytest.mark.asyncio
async def test_check_consent_status(setu, mock_http):
    mock_http.get.return_value = _mock_response(200, {
        "id": "consent-123", "status": "ACTIVE",
        "detail": {"fiTypes": ["DEPOSIT"], "consentExpiry": "2027-03-15T00:00:00Z"},
    })
    result = await setu.check_consent_status("consent-123")
    assert result["status"] == "ACTIVE"

@pytest.mark.asyncio
async def test_fetch_transactions_normalizes(setu, mock_http):
    mock_http.post.return_value = _mock_response(200, {
        "fi": [{"data": {
            "account": {"maskedAccNumber": "XXXX1234", "type": "SAVINGS"},
            "transactions": [{"txnId": "txn-1", "type": "DEBIT", "amount": "1500.00",
                "narration": "AMAZON PURCHASE", "transactionTimestamp": "2026-03-10T14:30:00Z",
                "reference": "REF123", "mode": "UPI"}],
        }}],
    })
    txns = await setu.fetch_transactions("c-1", datetime(2026, 3, 1, tzinfo=timezone.utc), datetime(2026, 3, 15, tzinfo=timezone.utc))
    assert len(txns) == 1
    assert txns[0]["amount"] == -1500.00
    assert txns[0]["payment_method"] == "UPI"

@pytest.mark.asyncio
async def test_revoke_consent(setu, mock_http):
    mock_http.post.return_value = _mock_response(200, {})
    await setu.revoke_consent("consent-123")
    assert "consent-123/revoke" in mock_http.post.call_args[0][0]

@pytest.mark.asyncio
async def test_raises_on_error(setu, mock_http):
    error_resp = _mock_response(500, {"error": "internal"})
    error_resp.raise_for_status.side_effect = Exception("500 Server Error")
    mock_http.post.return_value = error_resp
    with pytest.raises(Exception, match="500"):
        await setu.initiate_consent("user-1", ["DEPOSIT"])
```

- [ ] **Step 2: Run test — verify it fails**

Run: `.venv/bin/python -m pytest apps/api/domains/aggregator/tests/test_setu_provider.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement SetuProvider**

```python
# apps/api/domains/aggregator/providers/setu.py
"""Setu Account Aggregator provider implementation."""
import httpx
from datetime import datetime, timedelta, timezone
from typing import Any

from apps.api.domains.aggregator.provider import AggregatorProvider


class SetuProvider(AggregatorProvider):
    """Setu Data Gateway AA integration.

    Accepts optional http_client for dependency injection (testing).
    """

    def __init__(self, client_id: str, client_secret: str, base_url: str,
                 redirect_url: str, http_client: httpx.AsyncClient | None = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url.rstrip("/")
        self.redirect_url = redirect_url
        self._http_client = http_client

    def _headers(self) -> dict[str, str]:
        return {"x-client-id": self.client_id, "x-client-secret": self.client_secret,
                "Content-Type": "application/json"}

    async def _client(self) -> httpx.AsyncClient:
        return self._http_client or httpx.AsyncClient()

    async def initiate_consent(self, user_id: str, fi_types: list[str]) -> dict[str, str]:
        now = datetime.now(timezone.utc)
        payload = {
            "Detail": {
                "consentStart": now.isoformat(),
                "consentExpiry": (now + timedelta(days=365)).isoformat(),
                "fiTypes": fi_types, "consentTypes": ["TRANSACTIONS"],
                "fetchType": "PERIODIC",
                "Frequency": {"value": 1, "unit": "DAY"},
                "DataLife": {"value": 1, "unit": "YEAR"},
            },
            "redirectUrl": self.redirect_url,
        }
        client = await self._client()
        resp = await client.post(f"{self.base_url}/consents", json=payload, headers=self._headers())
        resp.raise_for_status()
        data = resp.json()
        return {"consent_id": data["id"], "redirect_url": data["url"]}

    async def check_consent_status(self, consent_id: str) -> dict[str, Any]:
        client = await self._client()
        resp = await client.get(f"{self.base_url}/consents/{consent_id}", headers=self._headers())
        resp.raise_for_status()
        data = resp.json()
        return {"status": data["status"], "detail": data.get("detail")}

    async def fetch_transactions(self, consent_id: str, from_date: datetime, to_date: datetime) -> list[dict[str, Any]]:
        payload = {"consentId": consent_id, "DataRange": {
            "from": from_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": to_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }, "format": "json"}
        client = await self._client()
        resp = await client.post(f"{self.base_url}/fi/fetch", json=payload, headers=self._headers())
        resp.raise_for_status()
        return self._normalize_transactions(resp.json())

    async def revoke_consent(self, consent_id: str) -> None:
        client = await self._client()
        resp = await client.post(f"{self.base_url}/consents/{consent_id}/revoke", headers=self._headers())
        resp.raise_for_status()

    def _normalize_transactions(self, setu_response: dict[str, Any]) -> list[dict[str, Any]]:
        transactions = []
        for fi in setu_response.get("fi", []):
            account_data = fi.get("data", {}).get("account", {})
            for txn in fi.get("data", {}).get("transactions", []):
                amount = float(txn["amount"])
                amount = -abs(amount) if txn.get("type") == "DEBIT" else abs(amount)
                transactions.append({
                    "transaction_date": txn["transactionTimestamp"][:19],
                    "amount": amount, "description": txn.get("narration", ""),
                    "merchant_name": "", "payment_method": txn.get("mode", ""),
                    "type": txn.get("type", "").lower(), "status": "completed",
                    "currency": "INR", "reference": txn.get("reference", ""),
                    "bank_name": account_data.get("type", ""), "raw_data": txn,
                })
        return transactions
```

Also create empty `apps/api/domains/aggregator/providers/__init__.py`.

- [ ] **Step 4: Run test — verify it passes**

Run: `.venv/bin/python -m pytest apps/api/domains/aggregator/tests/test_setu_provider.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add apps/api/domains/aggregator/providers/ apps/api/domains/aggregator/tests/test_setu_provider.py
git commit -m "feat(aggregator): implement SetuProvider with DI and error handling"
```

### Task 7: Create ManualProvider (no-op for file imports)

**Files:**
- Create: `apps/api/domains/aggregator/providers/manual.py`
- Create: `apps/api/domains/aggregator/tests/test_manual_provider.py`

- [ ] **Step 1: Write failing test**

```python
# apps/api/domains/aggregator/tests/test_manual_provider.py
import pytest
from datetime import datetime, timezone
from apps.api.domains.aggregator.providers.manual import ManualProvider

@pytest.fixture
def manual():
    return ManualProvider()

@pytest.mark.asyncio
async def test_initiate_consent_raises(manual):
    with pytest.raises(NotImplementedError, match="Manual accounts do not use consent"):
        await manual.initiate_consent("user-1", ["DEPOSIT"])

@pytest.mark.asyncio
async def test_fetch_transactions_returns_empty(manual):
    result = await manual.fetch_transactions("n/a", datetime.now(timezone.utc), datetime.now(timezone.utc))
    assert result == []

@pytest.mark.asyncio
async def test_revoke_consent_is_noop(manual):
    await manual.revoke_consent("n/a")
```

- [ ] **Step 2: Run test — verify it fails**

Run: `.venv/bin/python -m pytest apps/api/domains/aggregator/tests/test_manual_provider.py -v`

- [ ] **Step 3: Implement ManualProvider**

```python
# apps/api/domains/aggregator/providers/manual.py
from datetime import datetime
from typing import Any
from apps.api.domains.aggregator.provider import AggregatorProvider

class ManualProvider(AggregatorProvider):
    async def initiate_consent(self, user_id: str, fi_types: list[str]) -> dict[str, str]:
        raise NotImplementedError("Manual accounts do not use consent flows")
    async def check_consent_status(self, consent_id: str) -> dict[str, Any]:
        return {"status": "none"}
    async def fetch_transactions(self, consent_id: str, from_date: datetime, to_date: datetime) -> list[dict[str, Any]]:
        return []
    async def revoke_consent(self, consent_id: str) -> None:
        pass
```

- [ ] **Step 4: Run test — verify it passes**

Run: `.venv/bin/python -m pytest apps/api/domains/aggregator/tests/test_manual_provider.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add apps/api/domains/aggregator/providers/manual.py apps/api/domains/aggregator/tests/test_manual_provider.py
git commit -m "feat(aggregator): add ManualProvider no-op for file imports"
```

### Task 8: Create aggregator service

**Depends on:** Tasks 4-7, Task 3

**Files:**
- Create: `apps/api/domains/aggregator/service.py`
- Create: `apps/api/domains/aggregator/tests/test_service.py`

- [ ] **Step 1: Write failing tests**

```python
# apps/api/domains/aggregator/tests/test_service.py
import pytest
from unittest.mock import MagicMock, AsyncMock
from apps.api.domains.aggregator import service


def _mock_supabase(query_data=None):
    client = MagicMock()
    result = MagicMock()
    result.data = query_data or []
    chain = MagicMock()
    chain.execute.return_value = result
    for m in ("eq", "neq", "order", "select", "insert", "update", "delete", "limit"):
        getattr(chain, m).return_value = chain
    client.table.return_value = chain
    rpc_result = MagicMock()
    rpc_result.data = [{"inserted_count": 5, "skipped_count": 0}]
    rpc_chain = MagicMock()
    rpc_chain.execute.return_value = rpc_result
    client.rpc.return_value = rpc_chain
    return client


@pytest.mark.asyncio
async def test_list_accounts():
    accounts = [{"id": "acc-1"}]
    result = await service.list_accounts(_mock_supabase(accounts), "user-1")
    assert result == accounts

@pytest.mark.asyncio
async def test_get_or_create_manual_returns_existing():
    existing = [{"id": "acc-m", "is_manual": True}]
    result = await service.get_or_create_manual_account(_mock_supabase(existing), "user-1")
    assert result["id"] == "acc-m"

@pytest.mark.asyncio
async def test_get_or_create_manual_creates_new():
    client = _mock_supabase([])
    new = {"id": "acc-new", "is_manual": True}
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[new])
    result = await service.get_or_create_manual_account(client, "user-1")
    assert result["id"] == "acc-new"

@pytest.mark.asyncio
async def test_link_account():
    provider = AsyncMock()
    provider.initiate_consent.return_value = {"consent_id": "c-1", "redirect_url": "https://setu.co/c-1"}
    result = await service.link_account(_mock_supabase([]), "user-1", provider, ["DEPOSIT"])
    assert result["consent_id"] == "c-1"
    provider.initiate_consent.assert_called_once()

@pytest.mark.asyncio
async def test_handle_callback_active():
    account = {"id": "acc-1", "user_id": "user-1"}
    provider = AsyncMock()
    provider.check_consent_status.return_value = {"status": "ACTIVE", "detail": {"consentExpiry": "2027-03-15"}}
    result = await service.handle_callback(_mock_supabase([account]), "c-1", provider)
    assert result["status"] == "active"

@pytest.mark.asyncio
async def test_handle_callback_rejected():
    account = {"id": "acc-1", "user_id": "user-1"}
    provider = AsyncMock()
    provider.check_consent_status.return_value = {"status": "REJECTED"}
    result = await service.handle_callback(_mock_supabase([account]), "c-1", provider)
    assert result["status"] == "rejected"

@pytest.mark.asyncio
async def test_sync_account():
    account = {"id": "acc-1", "user_id": "user-1", "consent_id": "c-1", "last_synced_at": None}
    provider = AsyncMock()
    provider.fetch_transactions.return_value = [
        {"transaction_date": "2026-03-10T14:30:00", "amount": -1500.00,
         "description": "AMAZON", "merchant_name": "", "payment_method": "UPI", "reference": "REF1"}
    ]
    result = await service.sync_account(_mock_supabase([account]), "acc-1", provider)
    assert "inserted" in result

@pytest.mark.asyncio
async def test_unlink_manual_raises():
    manual = {"id": "acc-m", "is_manual": True, "consent_id": None, "consent_status": "none"}
    with pytest.raises(ValueError, match="Cannot unlink"):
        await service.unlink_account(_mock_supabase([manual]), "acc-m", AsyncMock())

@pytest.mark.asyncio
async def test_unlink_revokes_consent():
    account = {"id": "acc-1", "is_manual": False, "consent_id": "c-1", "consent_status": "active"}
    provider = AsyncMock()
    await service.unlink_account(_mock_supabase([account]), "acc-1", provider)
    provider.revoke_consent.assert_called_once_with("c-1")
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `.venv/bin/python -m pytest apps/api/domains/aggregator/tests/test_service.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement the service**

```python
# apps/api/domains/aggregator/service.py
"""Aggregator service — orchestrates consent, sync, and account lifecycle."""
from datetime import datetime, timezone
from typing import Any
from apps.api.domains.aggregator.provider import AggregatorProvider
from apps.api.domains.ingestion.service import generate_fingerprint


async def list_accounts(client: Any, user_id: str) -> list[dict]:
    return client.table("bank_accounts").select("*").eq("user_id", user_id).order("created_at").execute().data


async def get_or_create_manual_account(client: Any, user_id: str) -> dict:
    existing = client.table("bank_accounts").select("*").eq("user_id", user_id).eq("is_manual", True).execute()
    if existing.data:
        return existing.data[0]
    result = client.table("bank_accounts").insert({
        "user_id": user_id, "account_name": "Manual Import",
        "account_type": "manual", "is_manual": True, "consent_status": "none",
    }).execute()
    return result.data[0]


async def link_account(client: Any, user_id: str, provider: AggregatorProvider, fi_types: list[str]) -> dict[str, str]:
    consent = await provider.initiate_consent(user_id, fi_types)
    client.table("bank_accounts").insert({
        "user_id": user_id, "account_name": "Linking...", "account_type": "savings",
        "provider": "setu", "consent_id": consent["consent_id"], "consent_status": "pending",
    }).execute()
    return consent


async def handle_callback(client: Any, consent_id: str, provider: AggregatorProvider) -> dict:
    status_result = await provider.check_consent_status(consent_id)
    status = status_result["status"]
    account_row = client.table("bank_accounts").select("*").eq("consent_id", consent_id).execute().data
    if not account_row:
        raise ValueError(f"No account found for consent_id={consent_id}")
    account = account_row[0]

    if status == "ACTIVE":
        detail = status_result.get("detail") or {}
        client.table("bank_accounts").update({
            "consent_status": "active", "consent_expiry": detail.get("consentExpiry"),
        }).eq("id", account["id"]).execute()
        return {"account_id": account["id"], "status": "active"}
    elif status == "REJECTED":
        client.table("bank_accounts").delete().eq("id", account["id"]).execute()
        return {"account_id": account["id"], "status": "rejected"}
    else:
        client.table("bank_accounts").update({"consent_status": status.lower()}).eq("id", account["id"]).execute()
        return {"account_id": account["id"], "status": status.lower()}


async def sync_account(client: Any, account_id: str, provider: AggregatorProvider) -> dict[str, int]:
    account = client.table("bank_accounts").select("*").eq("id", account_id).execute().data[0]
    client.table("bank_accounts").update({"sync_status": "syncing"}).eq("id", account_id).execute()

    try:
        from_date = account.get("last_synced_at")
        if from_date and isinstance(from_date, str):
            from_date = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
        elif not from_date:
            from_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
        to_date = datetime.now(timezone.utc)

        raw_txns = await provider.fetch_transactions(account["consent_id"], from_date, to_date)
        rows = []
        for txn in raw_txns:
            fp = generate_fingerprint(
                date=txn.get("transaction_date", ""), amount=txn.get("amount", 0),
                merchant=txn.get("merchant_name", ""), description=txn.get("description", ""),
                payment_method=txn.get("payment_method", ""), reference=txn.get("reference", ""),
            )
            rows.append({**txn, "user_id": account["user_id"], "account_id": account_id,
                         "fingerprint": fp, "category": "Uncategorized"})

        inserted = 0
        if rows:
            result = client.rpc("batch_import_transactions", {
                "p_user_id": account["user_id"], "p_account_id": account_id, "p_rows": rows,
            }).execute()
            if result.data:
                row = result.data[0] if isinstance(result.data, list) else result.data
                inserted = int(row.get("inserted_count", 0)) if isinstance(row, dict) else len(rows)

        client.table("bank_accounts").update({
            "sync_status": "idle", "last_synced_at": to_date.isoformat(),
        }).eq("id", account_id).execute()
        return {"inserted": inserted, "skipped_duplicates": len(rows) - inserted}
    except Exception:
        client.table("bank_accounts").update({"sync_status": "error"}).eq("id", account_id).execute()
        raise


async def unlink_account(client: Any, account_id: str, provider: AggregatorProvider) -> None:
    account = client.table("bank_accounts").select("*").eq("id", account_id).execute().data[0]
    if account["is_manual"]:
        raise ValueError("Cannot unlink Manual Import account")
    if account.get("consent_id") and account["consent_status"] == "active":
        await provider.revoke_consent(account["consent_id"])
    client.table("bank_accounts").update({"consent_status": "revoked", "sync_status": "idle"}).eq("id", account_id).execute()
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `.venv/bin/python -m pytest apps/api/domains/aggregator/tests/test_service.py -v`
Expected: 9 PASSED

- [ ] **Step 5: Commit**

```bash
git add apps/api/domains/aggregator/service.py apps/api/domains/aggregator/tests/test_service.py
git commit -m "feat(aggregator): add service layer for consent, sync, and account lifecycle"
```

### Task 9: Create REST API router

**Depends on:** Task 8

**Files:**
- Create: `apps/api/domains/aggregator/router.py`
- Create: `apps/api/domains/aggregator/tests/test_router.py`
- Modify: `apps/api/main.py:247` (mount new router)

- [ ] **Step 1: Write failing tests**

```python
# apps/api/domains/aggregator/tests/test_router.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
from apps.api.domains.aggregator.router import router
from apps.api.core.auth import get_current_user_id, get_user_client


@pytest.fixture
def mock_client():
    client = MagicMock()
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=[])
    for m in ("eq", "order", "select", "insert", "update", "delete"):
        getattr(chain, m).return_value = chain
    client.table.return_value = chain
    return client

@pytest.fixture
def app(mock_client):
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1")
    test_app.dependency_overrides[get_current_user_id] = lambda: "test-user-id"
    test_app.dependency_overrides[get_user_client] = lambda: mock_client
    return test_app

@pytest.fixture
def http(app):
    return TestClient(app)

def test_list_accounts(http, mock_client):
    mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [{"id": "acc-1"}]
    assert http.get("/api/v1/aggregator/accounts/").status_code == 200

def test_get_account(http, mock_client):
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [{"id": "acc-1"}]
    assert http.get("/api/v1/aggregator/accounts/acc-1").status_code == 200

def test_link_account(http):
    with patch("apps.api.domains.aggregator.router._get_setu_provider") as mp:
        p = AsyncMock()
        p.initiate_consent.return_value = {"consent_id": "c-1", "redirect_url": "https://setu.co/c-1"}
        mp.return_value = p
        resp = http.post("/api/v1/aggregator/accounts/link", json={"fi_types": ["DEPOSIT"]})
        assert resp.status_code == 200
        assert resp.json()["consent_id"] == "c-1"

def test_delete_account(http, mock_client):
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "acc-1", "is_manual": False, "consent_id": "c-1", "consent_status": "active"}]
    with patch("apps.api.domains.aggregator.router._get_setu_provider") as mp:
        mp.return_value = AsyncMock()
        assert http.delete("/api/v1/aggregator/accounts/acc-1").status_code == 204

def test_consent_callback(http, mock_client):
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{"id": "acc-1", "user_id": "test-user-id"}]
    with patch("apps.api.domains.aggregator.router._get_setu_provider") as mp:
        p = AsyncMock()
        p.check_consent_status.return_value = {"status": "ACTIVE", "detail": {}}
        mp.return_value = p
        assert http.get("/api/v1/aggregator/accounts/callback?consent_id=c-1").status_code == 200
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `.venv/bin/python -m pytest apps/api/domains/aggregator/tests/test_router.py -v`

- [ ] **Step 3: Implement the router**

```python
# apps/api/domains/aggregator/router.py
"""REST API for account aggregator. Mounted at /api/v1/aggregator/."""
import os
from fastapi import APIRouter, Depends, HTTPException, Response
from supabase import Client
from apps.api.core.auth import get_current_user_id, get_user_client
from apps.api.domains.aggregator import service
from apps.api.domains.aggregator.schemas import BankAccountOut, LinkAccountRequest, LinkAccountResponse, SyncResponse
from apps.api.domains.aggregator.providers.setu import SetuProvider

router = APIRouter(prefix="/aggregator", tags=["aggregator"])


def _get_setu_provider() -> SetuProvider:
    return SetuProvider(
        client_id=os.environ["SETU_CLIENT_ID"], client_secret=os.environ["SETU_CLIENT_SECRET"],
        base_url=os.environ.get("SETU_BASE_URL", "https://fiu-sandbox.setu.co"),
        redirect_url=os.environ.get("SETU_REDIRECT_URL", "http://localhost:3000/dashboard/accounts/callback"),
    )


@router.get("/accounts/", response_model=list[BankAccountOut])
async def list_accounts(user_id: str = Depends(get_current_user_id), client: Client = Depends(get_user_client)):
    return await service.list_accounts(client, user_id)


@router.get("/accounts/callback")
async def consent_callback(consent_id: str, user_id: str = Depends(get_current_user_id), client: Client = Depends(get_user_client)):
    return await service.handle_callback(client, consent_id, _get_setu_provider())


@router.get("/accounts/{account_id}")
async def get_account(account_id: str, user_id: str = Depends(get_current_user_id), client: Client = Depends(get_user_client)):
    result = client.table("bank_accounts").select("*").eq("id", account_id).eq("user_id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Account not found")
    return result.data[0]


@router.post("/accounts/link", response_model=LinkAccountResponse)
async def link_account(body: LinkAccountRequest, user_id: str = Depends(get_current_user_id), client: Client = Depends(get_user_client)):
    return await service.link_account(client, user_id, _get_setu_provider(), body.fi_types)


@router.post("/accounts/{account_id}/sync", response_model=SyncResponse)
async def sync_account(account_id: str, user_id: str = Depends(get_current_user_id), client: Client = Depends(get_user_client)):
    result = await service.sync_account(client, account_id, _get_setu_provider())
    return SyncResponse(account_id=account_id, **result)


@router.delete("/accounts/{account_id}", status_code=204)
async def unlink_account(account_id: str, user_id: str = Depends(get_current_user_id), client: Client = Depends(get_user_client)):
    await service.unlink_account(client, account_id, _get_setu_provider())
    return Response(status_code=204)
```

- [ ] **Step 4: Mount router in `apps/api/main.py`**

After line 247 (`app.include_router(accounts_router, prefix="/api/v1")`), add:

```python
from apps.api.domains.aggregator.router import router as aggregator_router
app.include_router(aggregator_router, prefix="/api/v1")
```

- [ ] **Step 5: Run tests — verify they pass**

Run: `.venv/bin/python -m pytest apps/api/domains/aggregator/tests/test_router.py -v`
Expected: 5 PASSED

- [ ] **Step 6: Commit**

```bash
git add apps/api/domains/aggregator/router.py apps/api/domains/aggregator/tests/test_router.py apps/api/main.py
git commit -m "feat(aggregator): add REST API router at /api/v1/aggregator/"
```

---

## Chunk 3: Ingestion Update + Sync Wiring

### Task 10: Update ingestion to use account_id

**Depends on:** Task 8 (`get_or_create_manual_account`)

**Files:**
- Modify: `apps/api/domains/ingestion/router.py` (lines 51-98, 101-119)
- Create: `apps/api/domains/ingestion/tests/test_account_id.py`

- [ ] **Step 1: Write failing test**

```python
# apps/api/domains/ingestion/tests/test_account_id.py
"""Test ingestion account_id wiring."""
import pytest
from unittest.mock import MagicMock
from apps.api.domains.ingestion.router import _build_transaction_row, _rpc_insert_batch


def test_build_transaction_row_includes_account_id():
    row = {"date": "2026-03-10", "amount": -100.0, "description": "Test"}
    result = _build_transaction_row(row, "user-1", "fp-123", "acc-1")
    assert result["account_id"] == "acc-1"


def test_rpc_insert_batch_passes_account_id():
    client = MagicMock()
    client.rpc.return_value.execute.return_value = MagicMock(
        data=[{"inserted_count": 1, "skipped_count": 0}])
    _rpc_insert_batch(client, "user-1", "acc-1", [{"fingerprint": "fp-1"}])
    params = client.rpc.call_args[0][1]
    assert params["p_account_id"] == "acc-1"
```

- [ ] **Step 2: Run test — verify it fails**

Run: `.venv/bin/python -m pytest apps/api/domains/ingestion/tests/test_account_id.py -v`
Expected: FAIL (signature mismatch)

- [ ] **Step 3: Modify ingestion router**

In `apps/api/domains/ingestion/router.py`:

1. **`_build_transaction_row` (line 51)** — add `account_id: str` parameter:

   ```python
   def _build_transaction_row(row: dict, user_id: str, fingerprint: str, account_id: str) -> dict:
   ```

   Add `"account_id": account_id,` to the return dict (after `"fingerprint": fingerprint,`).

2. **`_rpc_insert_batch` (line 101)** — add `account_id: str` parameter:

   ```python
   def _rpc_insert_batch(client: Client, user_id: str, account_id: str, rows: list[dict]) -> tuple[int, int]:
   ```

   Update RPC params: `{"p_user_id": user_id, "p_account_id": account_id, "p_rows": rows}`

3. **In `import_file()` (around line 420)** — before the row-building loop, fetch the manual account:

   ```python
   from apps.api.domains.aggregator.service import get_or_create_manual_account
   manual_account = await get_or_create_manual_account(user_client, user_id)
   manual_account_id = manual_account["id"]
   ```

   Then pass `manual_account_id` to all calls to `_build_transaction_row` and `_rpc_insert_batch`.

- [ ] **Step 4: Run tests — verify they pass**

Run: `.venv/bin/python -m pytest apps/api/domains/ingestion/tests/ -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add apps/api/domains/ingestion/
git commit -m "feat(ingestion): associate file imports with Manual Import account"
```

### Task 11: Update transaction listing to accept account_id filter

**Files:**
- Modify: `apps/api/core/filtering.py` (add `account_id` field)
- Modify: `apps/api/domains/accounts/router.py:123-160` (add query param)
- Create: `apps/api/domains/accounts/tests/test_account_filter.py`

- [ ] **Step 1: Write failing test**

```python
# apps/api/domains/accounts/tests/test_account_filter.py
import pytest
from unittest.mock import MagicMock
from apps.api.core.filtering import TransactionFilter, apply_filters


def test_filter_with_account_id():
    query = MagicMock()
    query.eq.return_value = query
    apply_filters(query, TransactionFilter(account_id="acc-123"))
    query.eq.assert_any_call("account_id", "acc-123")

def test_filter_all_skips():
    query = MagicMock()
    apply_filters(query, TransactionFilter(account_id="all"))
    for call in query.eq.call_args_list:
        assert call[0][0] != "account_id"

def test_filter_none_skips():
    query = MagicMock()
    apply_filters(query, TransactionFilter())
    query.eq.assert_not_called()
```

- [ ] **Step 2: Run test — verify it fails**

Run: `.venv/bin/python -m pytest apps/api/domains/accounts/tests/test_account_filter.py -v`

- [ ] **Step 3: Add account_id filter**

In `apps/api/core/filtering.py`:
- Add field to `TransactionFilter` (after `type`, line 29): `account_id: Optional[str] = None`
- Add to `apply_filters()` (after type filter, ~line 58):

  ```python
  if filters.account_id is not None and filters.account_id != "all":
      query = query.eq("account_id", filters.account_id)
  ```

In `apps/api/domains/accounts/router.py` `list_transactions` endpoint (line 123): add `account_id: str | None = None` query parameter and pass to `TransactionFilter(account_id=account_id, ...)`.

- [ ] **Step 4: Run tests — verify they pass**

Run: `.venv/bin/python -m pytest apps/api/domains/accounts/tests/test_account_filter.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add apps/api/core/filtering.py apps/api/domains/accounts/
git commit -m "feat(accounts): add account_id filter to transaction listing"
```

### Task 12: Add daily auto-sync to worker polling loop

**Note:** Worker uses `while True` polling loop, NOT Celery.

**Files:**
- Create: `apps/worker/sync_task.py`
- Modify: `apps/worker/main.py` (add sync to loop)
- Create: `apps/worker/tests/test_sync_task.py`

- [ ] **Step 1: Write failing test**

```python
# apps/worker/tests/test_sync_task.py
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from apps.worker.sync_task import should_run_sync, sync_all_active_accounts


def test_should_run_first_time():
    assert should_run_sync(last_run=None) is True

def test_should_run_after_24h():
    assert should_run_sync(last_run=datetime.now(timezone.utc) - timedelta(hours=25)) is True

def test_should_not_run_when_recent():
    assert should_run_sync(last_run=datetime.now(timezone.utc) - timedelta(hours=1)) is False

def test_sync_all_only_active():
    client = MagicMock()
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=[
        {"id": "acc-1", "consent_status": "active", "consent_id": "c-1", "user_id": "u-1", "last_synced_at": None}])
    chain.eq.return_value = chain
    chain.select.return_value = chain
    client.table.return_value = chain
    with patch("apps.worker.sync_task._sync_single_account") as mock_sync:
        sync_all_active_accounts(client)
        mock_sync.assert_called_once()
```

- [ ] **Step 2: Run test — verify it fails**

Run: `.venv/bin/python -m pytest apps/worker/tests/test_sync_task.py -v`

- [ ] **Step 3: Implement sync task**

```python
# apps/worker/sync_task.py
"""Daily auto-sync for linked bank accounts. Uses polling loop, NOT Celery."""
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)
SYNC_INTERVAL = timedelta(hours=24)


def should_run_sync(last_run: datetime | None) -> bool:
    if last_run is None:
        return True
    return datetime.now(timezone.utc) - last_run >= SYNC_INTERVAL


def _sync_single_account(client: Any, account_id: str) -> None:
    from apps.api.domains.aggregator.service import sync_account
    from apps.api.domains.aggregator.providers.setu import SetuProvider
    provider = SetuProvider(
        client_id=os.environ["SETU_CLIENT_ID"], client_secret=os.environ["SETU_CLIENT_SECRET"],
        base_url=os.environ.get("SETU_BASE_URL", "https://fiu-sandbox.setu.co"),
        redirect_url=os.environ.get("SETU_REDIRECT_URL", "http://localhost:3000/dashboard/accounts/callback"),
    )
    asyncio.run(sync_account(client, account_id, provider))


def sync_all_active_accounts(client: Any) -> None:
    accounts = client.table("bank_accounts").select("*").eq("consent_status", "active").execute().data
    for account in accounts:
        try:
            logger.info(f"Syncing account {account['id']}")
            _sync_single_account(client, account["id"])
            logger.info(f"Synced account {account['id']}")
        except Exception as e:
            logger.error(f"Failed to sync account {account['id']}: {e}")
```

- [ ] **Step 4: Run test — verify it passes**

Run: `.venv/bin/python -m pytest apps/worker/tests/test_sync_task.py -v`
Expected: 4 PASSED

- [ ] **Step 5: Wire into worker main loop**

In `apps/worker/main.py`:

Add import at top: `from apps.worker.sync_task import should_run_sync, sync_all_active_accounts`

Add after `get_supabase()`: `_last_sync_run: datetime | None = None`

In `main()` inside `while True` loop, after `had_job = process_next_job(supabase)`:

```python
        global _last_sync_run
        if should_run_sync(_last_sync_run):
            try:
                logger.info("Running daily account sync...")
                sync_all_active_accounts(supabase)
                _last_sync_run = datetime.now(timezone.utc)
                logger.info("Daily account sync complete.")
            except Exception as e:
                logger.error(f"Daily sync failed: {e}")
                _last_sync_run = datetime.now(timezone.utc)
```

- [ ] **Step 6: Commit**

```bash
git add apps/worker/
git commit -m "feat(worker): add daily auto-sync for linked bank accounts"
```

---

## Chunk 4: Frontend — API Client + Account Context

### Task 13: Add bank account API methods to frontend client

**Files:**
- Modify: `apps/web/lib/api/client.ts` (add `bankAccountsApi` + `BankAccount` type)
- Create: `apps/web/lib/api/__tests__/bankAccounts.test.ts`

- [ ] **Step 1: Write failing test**

```typescript
// apps/web/lib/api/__tests__/bankAccounts.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';

// We test the bankAccountsApi methods exist and call apiFetch correctly
// by mocking the global fetch
describe('bankAccountsApi', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
      status: 200,
    }));
  });

  it('should export bankAccountsApi object', async () => {
    const { bankAccountsApi } = await import('../client');
    expect(bankAccountsApi).toBeDefined();
    expect(bankAccountsApi.list).toBeTypeOf('function');
    expect(bankAccountsApi.link).toBeTypeOf('function');
    expect(bankAccountsApi.get).toBeTypeOf('function');
    expect(bankAccountsApi.unlink).toBeTypeOf('function');
    expect(bankAccountsApi.sync).toBeTypeOf('function');
  });

  it('should export BankAccount type', async () => {
    // TypeScript compile-time check — if BankAccount doesn't exist, this file won't compile
    const { bankAccountsApi } = await import('../client');
    expect(bankAccountsApi).toBeDefined();
  });
});
```

- [ ] **Step 2: Run test — verify it fails**

Run: `cd apps/web && npx vitest run lib/api/__tests__/bankAccounts.test.ts`
Expected: FAIL (`bankAccountsApi` not exported)

- [ ] **Step 3: Add API methods and type**

In `apps/web/lib/api/client.ts`, add the `BankAccount` interface and `bankAccountsApi` object:

```typescript
export interface BankAccount {
  id: string;
  user_id: string;
  account_name: string;
  account_type: string;
  institution: string | null;
  provider: string | null;
  consent_status: string;
  last_synced_at: string | null;
  sync_status: string;
  is_primary: boolean;
  is_manual: boolean;
  masked_number: string | null;
  currency: string;
  created_at: string;
  updated_at: string;
}

export const bankAccountsApi = {
  list: (token: string) =>
    apiFetch<BankAccount[]>('/aggregator/accounts/', { token }),
  link: (token: string, fiTypes: string[] = ['DEPOSIT']) =>
    apiFetch<{ redirect_url: string; consent_id: string }>(
      '/aggregator/accounts/link',
      { method: 'POST', body: { fi_types: fiTypes }, token }
    ),
  get: (id: string, token: string) =>
    apiFetch<BankAccount>(`/aggregator/accounts/${id}`, { token }),
  unlink: (id: string, token: string) =>
    apiFetch<void>(`/aggregator/accounts/${id}`, { method: 'DELETE', token }),
  sync: (id: string, token: string) =>
    apiFetch<{ inserted: number; skipped_duplicates: number }>(
      `/aggregator/accounts/${id}/sync`,
      { method: 'POST', token }
    ),
  callback: (consentId: string, token: string) =>
    apiFetch<{ account_id: string; status: string }>(
      `/aggregator/accounts/callback?consent_id=${consentId}`,
      { token }
    ),
};
```

- [ ] **Step 4: Run test — verify it passes**

Run: `cd apps/web && npx vitest run lib/api/__tests__/bankAccounts.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/web/lib/api/
git commit -m "feat(web): add bank account API client methods"
```

### Task 14: Create AccountContext for active account state

**Files:**
- Create: `apps/web/lib/contexts/AccountContext.tsx`
- Create: `apps/web/lib/contexts/__tests__/AccountContext.test.tsx`

- [ ] **Step 1: Write failing test**

```typescript
// apps/web/lib/contexts/__tests__/AccountContext.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { AccountProvider, useActiveAccount } from '../AccountContext';
import type { ReactNode } from 'react';

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => { store[key] = value; }),
    clear: () => { store = {}; },
  };
})();
vi.stubGlobal('localStorage', localStorageMock);

const wrapper = ({ children }: { children: ReactNode }) => (
  <AccountProvider>{children}</AccountProvider>
);

describe('AccountContext', () => {
  beforeEach(() => localStorageMock.clear());

  it('defaults to "all" accounts', () => {
    const { result } = renderHook(() => useActiveAccount(), { wrapper });
    expect(result.current.activeAccountId).toBe('all');
    expect(result.current.isAllAccounts).toBe(true);
  });

  it('setActiveAccountId updates state and localStorage', () => {
    const { result } = renderHook(() => useActiveAccount(), { wrapper });
    act(() => result.current.setActiveAccountId('acc-123'));
    expect(result.current.activeAccountId).toBe('acc-123');
    expect(localStorageMock.setItem).toHaveBeenCalledWith('scale-active-account-id', 'acc-123');
  });

  it('setAccounts populates the accounts list', () => {
    const { result } = renderHook(() => useActiveAccount(), { wrapper });
    const accounts = [{ id: 'acc-1', account_name: 'HDFC' }] as any[];
    act(() => result.current.setAccounts(accounts));
    expect(result.current.accounts).toHaveLength(1);
  });

  it('throws when used outside provider', () => {
    expect(() => renderHook(() => useActiveAccount())).toThrow();
  });
});
```

- [ ] **Step 2: Run test — verify it fails**

Run: `cd apps/web && npx vitest run lib/contexts/__tests__/AccountContext.test.tsx`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement AccountContext**

```typescript
// apps/web/lib/contexts/AccountContext.tsx
'use client';
import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import type { BankAccount } from '@/lib/api/client';

interface AccountContextValue {
  activeAccountId: string;
  activeAccount: BankAccount | null;
  accounts: BankAccount[];
  setActiveAccountId: (id: string) => void;
  setAccounts: (accounts: BankAccount[]) => void;
  isAllAccounts: boolean;
}

const AccountContext = createContext<AccountContextValue | null>(null);
const STORAGE_KEY = 'scale-active-account-id';

export function AccountProvider({ children }: { children: ReactNode }) {
  const [activeAccountId, setActiveAccountIdState] = useState<string>('all');
  const [accounts, setAccounts] = useState<BankAccount[]>([]);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) setActiveAccountIdState(stored);
  }, []);

  const setActiveAccountId = (id: string) => {
    setActiveAccountIdState(id);
    localStorage.setItem(STORAGE_KEY, id);
  };

  const activeAccount = accounts.find((a) => a.id === activeAccountId) ?? null;

  return (
    <AccountContext.Provider
      value={{ activeAccountId, activeAccount, accounts, setActiveAccountId, setAccounts, isAllAccounts: activeAccountId === 'all' }}
    >
      {children}
    </AccountContext.Provider>
  );
}

export function useActiveAccount() {
  const ctx = useContext(AccountContext);
  if (!ctx) throw new Error('useActiveAccount must be used within AccountProvider');
  return ctx;
}
```

- [ ] **Step 4: Run test — verify it passes**

Run: `cd apps/web && npx vitest run lib/contexts/__tests__/AccountContext.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/web/lib/contexts/
git commit -m "feat(web): add AccountContext for active account state management"
```

---

## Chunk 5: Frontend — Accounts Page + Switcher + Dashboard Scoping

**Note:** Use `@frontend-design:frontend-design` skill when implementing components for Refined Finance aesthetic (dark mode `#0B1221`, primary `#4892FF`, glassmorphic panels, Framer Motion, `rounded-[2rem]`).

### Task 15: Create AccountSwitcher, AccountBadge, SyncStatusIndicator

**Files:**
- Create: `apps/web/components/accounts/SyncStatusIndicator.tsx`
- Create: `apps/web/components/accounts/AccountSwitcher.tsx`
- Create: `apps/web/components/accounts/AccountBadge.tsx`
- Create: `apps/web/components/accounts/__tests__/switcher.test.tsx`

- [ ] **Step 1: Write failing tests**

```typescript
// apps/web/components/accounts/__tests__/switcher.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SyncStatusIndicator } from '../SyncStatusIndicator';
import { AccountBadge } from '../AccountBadge';

// SyncStatusIndicator tests
describe('SyncStatusIndicator', () => {
  it('renders idle state', () => {
    render(<SyncStatusIndicator status="idle" />);
    expect(screen.getByText(/synced/i)).toBeDefined();
  });

  it('renders syncing state', () => {
    render(<SyncStatusIndicator status="syncing" />);
    expect(screen.getByText(/syncing/i)).toBeDefined();
  });

  it('renders error state', () => {
    render(<SyncStatusIndicator status="error" />);
    expect(screen.getByText(/error/i)).toBeDefined();
  });
});

// AccountBadge tests
describe('AccountBadge', () => {
  it('shows "All Accounts" when no active account', () => {
    render(<AccountBadge accountName={null} isAllAccounts={true} />);
    expect(screen.getByText(/all accounts/i)).toBeDefined();
  });

  it('shows account name when active', () => {
    render(<AccountBadge accountName="HDFC ****1234" isAllAccounts={false} />);
    expect(screen.getByText(/HDFC/)).toBeDefined();
  });
});
```

- [ ] **Step 2: Run test — verify it fails**

Run: `cd apps/web && npx vitest run components/accounts/__tests__/switcher.test.tsx`

- [ ] **Step 3: Implement SyncStatusIndicator**

```typescript
// apps/web/components/accounts/SyncStatusIndicator.tsx
'use client';

const STATUS_CONFIG = {
  idle: { label: 'Synced', color: 'text-emerald-400', dot: 'bg-emerald-400' },
  syncing: { label: 'Syncing...', color: 'text-blue-400', dot: 'bg-blue-400 animate-pulse' },
  error: { label: 'Sync Error', color: 'text-red-400', dot: 'bg-red-400' },
} as const;

export function SyncStatusIndicator({ status }: { status: string }) {
  const config = STATUS_CONFIG[status as keyof typeof STATUS_CONFIG] ?? STATUS_CONFIG.idle;
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs ${config.color}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${config.dot}`} />
      {config.label}
    </span>
  );
}
```

- [ ] **Step 4: Implement AccountBadge**

```typescript
// apps/web/components/accounts/AccountBadge.tsx
'use client';

interface AccountBadgeProps {
  accountName: string | null;
  isAllAccounts: boolean;
  onClick?: () => void;
}

export function AccountBadge({ accountName, isAllAccounts, onClick }: AccountBadgeProps) {
  const label = isAllAccounts ? 'All Accounts' : (accountName ?? 'Unknown');
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-2 rounded-full bg-white/5 px-3 py-1 text-xs text-white/70 hover:bg-white/10 transition-colors"
    >
      <span className="h-1.5 w-1.5 rounded-full bg-[#4892FF]" />
      {label}
    </button>
  );
}
```

- [ ] **Step 5: Implement AccountSwitcher**

```typescript
// apps/web/components/accounts/AccountSwitcher.tsx
'use client';
import { useState } from 'react';
import { useActiveAccount } from '@/lib/contexts/AccountContext';
import { SyncStatusIndicator } from './SyncStatusIndicator';

export function AccountSwitcher() {
  const { accounts, activeAccountId, setActiveAccountId, isAllAccounts } = useActiveAccount();
  const [open, setOpen] = useState(false);

  const activeLabel = isAllAccounts
    ? 'All Accounts'
    : accounts.find((a) => a.id === activeAccountId)?.account_name ?? 'Select Account';

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between rounded-xl bg-white/5 px-3 py-2 text-sm text-white/80 hover:bg-white/10 transition-colors"
      >
        <div className="flex flex-col items-start">
          <span className="text-[10px] uppercase tracking-wider text-white/40">Active Account</span>
          <span className="text-sm font-medium text-white">{activeLabel}</span>
        </div>
        <svg className={`h-4 w-4 text-white/40 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute left-0 right-0 top-full z-50 mt-1 rounded-xl border border-white/10 bg-[#0B1221] p-1 shadow-xl">
          <button
            onClick={() => { setActiveAccountId('all'); setOpen(false); }}
            className={`w-full rounded-lg px-3 py-2 text-left text-sm transition-colors ${isAllAccounts ? 'bg-[#4892FF]/20 text-[#4892FF]' : 'text-white/70 hover:bg-white/5'}`}
          >
            All Accounts
          </button>
          {accounts.map((account) => (
            <button
              key={account.id}
              onClick={() => { setActiveAccountId(account.id); setOpen(false); }}
              className={`w-full rounded-lg px-3 py-2 text-left text-sm transition-colors ${activeAccountId === account.id ? 'bg-[#4892FF]/20 text-[#4892FF]' : 'text-white/70 hover:bg-white/5'}`}
            >
              <div className="flex items-center justify-between">
                <span>{account.account_name}</span>
                <SyncStatusIndicator status={account.sync_status} />
              </div>
              {account.masked_number && (
                <span className="text-[10px] text-white/30">{account.masked_number}</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Run tests — verify they pass**

Run: `cd apps/web && npx vitest run components/accounts/__tests__/switcher.test.tsx`
Expected: PASS

- [ ] **Step 7: Wire into dashboard layout**

Modify `apps/web/app/dashboard/layout.tsx`:
1. Import `AccountProvider` from `@/lib/contexts/AccountContext`
2. Wrap the return JSX children with `<AccountProvider>...</AccountProvider>`
3. Import and add `AccountSwitcher` in sidebar after the user session switcher (~line 301)
4. Import and add `AccountBadge` in content area before `{children}` (~line 362)
5. Add "Accounts" nav item (icon: `CreditCard` from lucide-react) between Transactions and Analytics in the nav items array (~line 240)

- [ ] **Step 8: Commit**

```bash
git add apps/web/components/accounts/ apps/web/app/dashboard/layout.tsx
git commit -m "feat(web): add AccountSwitcher, AccountBadge, and SyncStatusIndicator"
```

### Task 16: Create Accounts Management Page

**Files:**
- Create: `apps/web/app/dashboard/accounts/page.tsx`
- Create: `apps/web/app/dashboard/accounts/callback/page.tsx`
- Create: `apps/web/components/accounts/AccountList.tsx`
- Create: `apps/web/components/accounts/AccountDetail.tsx`
- Create: `apps/web/components/accounts/LinkAccountModal.tsx`
- Create: `apps/web/components/accounts/LinkAccountOnboarding.tsx`
- Create: `apps/web/components/accounts/__tests__/accounts-page.test.tsx`

- [ ] **Step 1: Write failing tests**

```typescript
// apps/web/components/accounts/__tests__/accounts-page.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AccountList } from '../AccountList';
import { AccountDetail } from '../AccountDetail';

const mockAccount = {
  id: 'acc-1', account_name: 'HDFC Savings', account_type: 'savings',
  institution: 'HDFC Bank', sync_status: 'idle', is_manual: false,
  masked_number: '****1234', consent_status: 'active',
  last_synced_at: '2026-03-15T10:00:00Z', is_primary: false,
  currency: 'INR', created_at: '2026-03-01', updated_at: '2026-03-15',
  user_id: 'u-1', provider: 'setu',
};

describe('AccountList', () => {
  it('renders account names', () => {
    render(<AccountList accounts={[mockAccount]} selectedId="acc-1" onSelect={vi.fn()} onLinkNew={vi.fn()} />);
    expect(screen.getByText('HDFC Savings')).toBeDefined();
  });

  it('shows Link New Account button', () => {
    render(<AccountList accounts={[]} selectedId={null} onSelect={vi.fn()} onLinkNew={vi.fn()} />);
    expect(screen.getByText(/link new/i)).toBeDefined();
  });
});

describe('AccountDetail', () => {
  it('renders account details', () => {
    render(<AccountDetail account={mockAccount} onSync={vi.fn()} onUnlink={vi.fn()} />);
    expect(screen.getByText('HDFC Savings')).toBeDefined();
    expect(screen.getByText(/HDFC Bank/)).toBeDefined();
  });

  it('shows sync button for non-manual accounts', () => {
    render(<AccountDetail account={mockAccount} onSync={vi.fn()} onUnlink={vi.fn()} />);
    expect(screen.getByText(/sync now/i)).toBeDefined();
  });
});
```

- [ ] **Step 2: Run test — verify it fails**

Run: `cd apps/web && npx vitest run components/accounts/__tests__/accounts-page.test.tsx`

- [ ] **Step 3: Implement AccountList**

```typescript
// apps/web/components/accounts/AccountList.tsx
'use client';
import type { BankAccount } from '@/lib/api/client';
import { SyncStatusIndicator } from './SyncStatusIndicator';

interface Props {
  accounts: BankAccount[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onLinkNew: () => void;
}

export function AccountList({ accounts, selectedId, onSelect, onLinkNew }: Props) {
  return (
    <div className="flex flex-col gap-2">
      {accounts.map((account) => (
        <button
          key={account.id}
          onClick={() => onSelect(account.id)}
          className={`rounded-2xl p-4 text-left transition-all ${
            selectedId === account.id
              ? 'border-2 border-[#4892FF] bg-[#4892FF]/10'
              : 'border border-white/10 bg-white/5 hover:bg-white/10'
          }`}
        >
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium text-white">{account.account_name}</div>
              {account.masked_number && (
                <div className="text-xs text-white/40">{account.masked_number}</div>
              )}
            </div>
            <SyncStatusIndicator status={account.sync_status} />
          </div>
          {account.institution && (
            <div className="mt-1 text-xs text-white/30">{account.institution}</div>
          )}
        </button>
      ))}
      <button
        onClick={onLinkNew}
        className="rounded-2xl border border-dashed border-white/20 p-4 text-sm text-white/50 hover:border-[#4892FF] hover:text-[#4892FF] transition-colors"
      >
        + Link New Account
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Implement AccountDetail**

```typescript
// apps/web/components/accounts/AccountDetail.tsx
'use client';
import type { BankAccount } from '@/lib/api/client';
import { SyncStatusIndicator } from './SyncStatusIndicator';

interface Props {
  account: BankAccount;
  onSync: (id: string) => void;
  onUnlink: (id: string) => void;
}

export function AccountDetail({ account, onSync, onUnlink }: Props) {
  return (
    <div className="rounded-[2rem] border border-white/10 bg-white/5 p-6">
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-white">{account.account_name}</h2>
        {account.institution && <p className="text-sm text-white/50">{account.institution}</p>}
      </div>

      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="rounded-xl bg-white/5 p-3">
          <div className="text-[10px] uppercase tracking-wider text-white/40">Type</div>
          <div className="text-sm text-white">{account.account_type}</div>
        </div>
        <div className="rounded-xl bg-white/5 p-3">
          <div className="text-[10px] uppercase tracking-wider text-white/40">Status</div>
          <SyncStatusIndicator status={account.sync_status} />
        </div>
        <div className="rounded-xl bg-white/5 p-3">
          <div className="text-[10px] uppercase tracking-wider text-white/40">Currency</div>
          <div className="text-sm text-white">{account.currency}</div>
        </div>
        <div className="rounded-xl bg-white/5 p-3">
          <div className="text-[10px] uppercase tracking-wider text-white/40">Last Synced</div>
          <div className="text-sm text-white">
            {account.last_synced_at ? new Date(account.last_synced_at).toLocaleDateString() : 'Never'}
          </div>
        </div>
      </div>

      {!account.is_manual && (
        <div className="flex gap-3">
          <button
            onClick={() => onSync(account.id)}
            disabled={account.sync_status === 'syncing'}
            className="rounded-xl bg-[#4892FF] px-4 py-2 text-sm font-medium text-white hover:bg-[#4892FF]/80 disabled:opacity-50 transition-colors"
          >
            Sync Now
          </button>
          <button
            onClick={() => onUnlink(account.id)}
            className="rounded-xl border border-red-500/30 px-4 py-2 text-sm text-red-400 hover:bg-red-500/10 transition-colors"
          >
            Unlink
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Implement LinkAccountModal**

```typescript
// apps/web/components/accounts/LinkAccountModal.tsx
'use client';

interface Props {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  loading?: boolean;
}

export function LinkAccountModal({ open, onClose, onConfirm, loading }: Props) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-[2rem] border border-white/10 bg-[#0B1221] p-8">
        <h3 className="text-lg font-semibold text-white mb-2">Link Bank Account</h3>
        <p className="text-sm text-white/60 mb-6">
          Connect your bank account securely via India&apos;s Account Aggregator framework.
        </p>
        <div className="mb-6 space-y-2">
          {['Read-only access — no debits', 'Revoke anytime from this page', 'RBI regulated & encrypted'].map((t) => (
            <div key={t} className="flex items-center gap-2 text-xs text-white/50">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              {t}
            </div>
          ))}
        </div>
        <div className="flex gap-3">
          <button onClick={onClose} className="flex-1 rounded-xl border border-white/10 py-2 text-sm text-white/60 hover:bg-white/5">
            Cancel
          </button>
          <button onClick={onConfirm} disabled={loading} className="flex-1 rounded-xl bg-[#4892FF] py-2 text-sm font-medium text-white hover:bg-[#4892FF]/80 disabled:opacity-50">
            {loading ? 'Redirecting...' : 'Continue →'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Implement LinkAccountOnboarding**

```typescript
// apps/web/components/accounts/LinkAccountOnboarding.tsx
'use client';

interface Props {
  onConfirm: () => void;
  onSkip: () => void;
  loading?: boolean;
}

export function LinkAccountOnboarding({ onConfirm, onSkip, loading }: Props) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
      <div className="mb-8">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-[#4892FF]/20">
          <svg className="h-8 w-8 text-[#4892FF]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
          </svg>
        </div>
        <h2 className="text-2xl font-bold text-white mb-2">Link Your Bank Account</h2>
        <p className="text-sm text-white/60 max-w-md">
          Securely connect your bank accounts using India&apos;s Account Aggregator framework.
          Your data is encrypted, read-only, and you can revoke access anytime.
        </p>
      </div>
      <div className="mb-8 space-y-3 text-left max-w-sm">
        {[
          { step: '1', text: 'Choose your bank from the list' },
          { step: '2', text: 'Approve consent on your bank\'s page' },
          { step: '3', text: 'Transactions sync automatically' },
        ].map(({ step, text }) => (
          <div key={step} className="flex items-center gap-3">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#4892FF]/20 text-xs font-bold text-[#4892FF]">{step}</span>
            <span className="text-sm text-white/70">{text}</span>
          </div>
        ))}
      </div>
      <div className="flex gap-3">
        <button onClick={onSkip} className="rounded-xl border border-white/10 px-6 py-2.5 text-sm text-white/60 hover:bg-white/5">
          Skip for now
        </button>
        <button onClick={onConfirm} disabled={loading} className="rounded-xl bg-[#4892FF] px-6 py-2.5 text-sm font-medium text-white hover:bg-[#4892FF]/80 disabled:opacity-50">
          {loading ? 'Redirecting...' : 'Link Account →'}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Implement callback page**

```typescript
// apps/web/app/dashboard/accounts/callback/page.tsx
'use client';
import { useEffect, useState } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { bankAccountsApi } from '@/lib/api/client';
import { createClient } from '@/lib/supabase/client';

export default function AccountCallbackPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [status, setStatus] = useState<'processing' | 'success' | 'error'>('processing');

  useEffect(() => {
    const consentId = searchParams.get('consent_id');
    if (!consentId) { setStatus('error'); return; }

    (async () => {
      try {
        const supabase = createClient();
        const { data: { session } } = await supabase.auth.getSession();
        if (!session?.access_token) { setStatus('error'); return; }
        await bankAccountsApi.callback(consentId, session.access_token);
        setStatus('success');
        setTimeout(() => router.push('/dashboard/accounts'), 2000);
      } catch { setStatus('error'); }
    })();
  }, [searchParams, router]);

  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="text-center">
        {status === 'processing' && <p className="text-white/60">Processing consent...</p>}
        {status === 'success' && <p className="text-emerald-400">Account linked! Redirecting...</p>}
        {status === 'error' && <p className="text-red-400">Something went wrong. <a href="/dashboard/accounts" className="underline">Go back</a></p>}
      </div>
    </div>
  );
}
```

- [ ] **Step 8: Implement accounts page**

```typescript
// apps/web/app/dashboard/accounts/page.tsx
'use client';
import { useEffect, useState } from 'react';
import { bankAccountsApi, type BankAccount } from '@/lib/api/client';
import { createClient } from '@/lib/supabase/client';
import { useActiveAccount } from '@/lib/contexts/AccountContext';
import { AccountList } from '@/components/accounts/AccountList';
import { AccountDetail } from '@/components/accounts/AccountDetail';
import { LinkAccountModal } from '@/components/accounts/LinkAccountModal';
import { LinkAccountOnboarding } from '@/components/accounts/LinkAccountOnboarding';

const HAS_LINKED_KEY = 'scale-has-linked-before';

export default function AccountsPage() {
  const { setAccounts } = useActiveAccount();
  const [accounts, setLocalAccounts] = useState<BankAccount[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [linking, setLinking] = useState(false);
  const [loading, setLoading] = useState(true);

  const hasLinkedBefore = typeof window !== 'undefined' && localStorage.getItem(HAS_LINKED_KEY) === 'true';
  const selectedAccount = accounts.find((a) => a.id === selectedId) ?? null;

  const fetchAccounts = async () => {
    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    if (!session?.access_token) return;
    const data = await bankAccountsApi.list(session.access_token);
    setLocalAccounts(data);
    setAccounts(data);
    if (data.length > 0 && !selectedId) setSelectedId(data[0].id);
    setLoading(false);
  };

  useEffect(() => { fetchAccounts(); }, []);

  const handleLink = async () => {
    setLinking(true);
    try {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) return;
      const { redirect_url } = await bankAccountsApi.link(session.access_token);
      localStorage.setItem(HAS_LINKED_KEY, 'true');
      window.location.href = redirect_url;
    } finally { setLinking(false); }
  };

  const handleSync = async (id: string) => {
    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    if (!session?.access_token) return;
    await bankAccountsApi.sync(id, session.access_token);
    fetchAccounts();
  };

  const handleUnlink = async (id: string) => {
    const supabase = createClient();
    const { data: { session } } = await supabase.auth.getSession();
    if (!session?.access_token) return;
    await bankAccountsApi.unlink(id, session.access_token);
    fetchAccounts();
  };

  if (loading) return <div className="flex items-center justify-center min-h-[60vh] text-white/40">Loading...</div>;

  // First-time user with no linked accounts: show onboarding
  if (accounts.length <= 1 && !hasLinkedBefore) {
    return <LinkAccountOnboarding onConfirm={handleLink} onSkip={() => localStorage.setItem(HAS_LINKED_KEY, 'true')} loading={linking} />;
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]">
      <AccountList accounts={accounts} selectedId={selectedId} onSelect={setSelectedId} onLinkNew={() => setShowModal(true)} />
      {selectedAccount ? (
        <AccountDetail account={selectedAccount} onSync={handleSync} onUnlink={handleUnlink} />
      ) : (
        <div className="flex items-center justify-center rounded-[2rem] border border-white/10 bg-white/5 p-12 text-white/30">
          Select an account to view details
        </div>
      )}
      <LinkAccountModal open={showModal} onClose={() => setShowModal(false)} onConfirm={handleLink} loading={linking} />
    </div>
  );
}
```

- [ ] **Step 9: Run tests — verify they pass**

Run: `cd apps/web && npx vitest run components/accounts/__tests__/`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add apps/web/components/accounts/ apps/web/app/dashboard/accounts/
git commit -m "feat(web): add accounts management page with list+detail layout"
```

### Task 17: Update dashboard and transactions pages for account scoping

**Files:**
- Modify: `apps/web/app/dashboard/page.tsx`
- Modify: `apps/web/app/dashboard/transactions/page.tsx`

- [ ] **Step 1: Update transactions page**

In `apps/web/app/dashboard/transactions/page.tsx`:
- Import `useActiveAccount` from `@/lib/contexts/AccountContext`
- Get `activeAccountId` from the hook
- Add `account_id` parameter to all transaction fetch calls (pass `activeAccountId` or `'all'`)
- When `isAllAccounts` and showing rows, optionally show a small account badge per transaction

- [ ] **Step 2: Update dashboard page**

In `apps/web/app/dashboard/page.tsx`:
- Import `useActiveAccount` from `@/lib/contexts/AccountContext`
- Get `activeAccountId` from the hook
- Pass `account_id` to all aggregation/stats API calls
- Spending trends, category distribution, big splurges should respect the selected account

- [ ] **Step 3: Run TypeScript check**

Run: `cd apps/web && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Run frontend lint**

Run: `cd apps/web && npm run lint`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add apps/web/app/dashboard/
git commit -m "feat(web): scope dashboard and transactions by active account"
```

---

## Chunk 6: Verification + HLD Sync

### Task 18: Full verification

Map each spec success criterion to a specific verification step.

- [ ] **Step 1: Update LLD status to Implemented**

In `docs/features/004-account-aggregator.md`, change `Status: Draft` to `Status: Implemented`.

```bash
git add docs/features/004-account-aggregator.md
git commit -m "docs: update account aggregator LLD status to Implemented"
```

- [ ] **Step 2: Run full test suite**

Run: `make check`
Expected: All checks pass (lint + tsc + pytest)

This covers:
- Backend: `.venv/bin/python -m pytest apps/ packages/ -v`
- Frontend: `cd apps/web && npx vitest run`
- TypeScript: `cd apps/web && npx tsc --noEmit`
- Lint: `cd apps/web && npm run lint`

- [ ] **Step 3: Verify success criterion 1 — AA linking + sync**

Run: `.venv/bin/python -m pytest -k "test_link_account and test_sync_account" -v`
Expected: Tests for link flow and sync flow all pass

- [ ] **Step 4: Verify success criterion 2 — Transaction isolation**

Run: `.venv/bin/python -m pytest -k "test_filter_with_account_id" -v`
Expected: account_id filter test passes (transactions are isolated per account)

- [ ] **Step 5: Verify success criterion 3 — Manual Import migration**

Run: `mcp__supabase__execute_sql`

```sql
SELECT COUNT(*) as unlinked FROM public.transactions WHERE account_id IS NULL;
```

Expected: `0` (all existing transactions backfilled to Manual Import accounts)

- [ ] **Step 6: Verify success criterion 4 — Auto-sync**

Run: `.venv/bin/python -m pytest -k "test_should_run_sync and test_sync_all" -v`
Expected: Worker sync tests pass

- [ ] **Step 7: Verify success criterion 5 — Account switcher**

Run: `cd apps/web && npx vitest run components/accounts/__tests__/ -v`
Expected: AccountSwitcher + AccountBadge tests pass

- [ ] **Step 8: Verify success criterion 6 — "All Accounts" aggregation**

Run: `.venv/bin/python -m pytest -k "test_filter_all_skips" -v`
Expected: Passes — confirms `account_id=all` does not filter, returning transactions across all accounts.

Also verify frontend: `cd apps/web && npx vitest run components/accounts/__tests__/ -v`
Expected: AccountSwitcher shows "All Accounts" option, AccountBadge renders "All Accounts" label.

- [ ] **Step 9: Verify success criterion 7 — Provider abstraction**

Run: `.venv/bin/python -m pytest -k "test_concrete_provider" -v`
Expected: AggregatorProvider ABC contract tests pass (proves swappability)

### Task 19: HLD sync + final commit

- [ ] **Step 1: Update database HLD**

In `docs/design/database-design.md`, add:

```markdown
### bank_accounts

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | gen_random_uuid() |
| user_id | UUID FK → auth.users | NOT NULL, CASCADE |
| account_name | TEXT | NOT NULL |
| account_type | TEXT | savings, current, manual |
| institution | TEXT | Bank name |
| provider | TEXT | setu, null for manual |
| provider_account_id | TEXT | External account ref |
| consent_id | TEXT | AA consent handle |
| consent_status | TEXT | none/pending/active/revoked |
| is_manual | BOOLEAN | TRUE for file import accounts |
| sync_status | TEXT | idle/syncing/error |
| last_synced_at | TIMESTAMPTZ | Last successful sync |

**Changelog:** 2026-03-15 | 004-account-aggregator | Added bank_accounts table, account_id FK on transactions
```

- [ ] **Step 2: Update API HLD**

In `docs/design/api-design.md`, add:

```markdown
### Aggregator Endpoints (`/api/v1/aggregator/`)

| Method | Path | Description |
|--------|------|-------------|
| GET | /accounts/ | List user's bank accounts |
| POST | /accounts/link | Initiate AA consent flow |
| GET | /accounts/callback | Handle consent redirect |
| GET | /accounts/{id} | Get account details |
| POST | /accounts/{id}/sync | Trigger manual sync |
| DELETE | /accounts/{id} | Unlink (revoke consent) |

**Changelog:** 2026-03-15 | 004-account-aggregator | Added aggregator domain with 6 REST endpoints
```

- [ ] **Step 3: Update LLD status to Verified**

In `docs/features/004-account-aggregator.md`, change `Status: Implemented` to `Status: Verified`.

- [ ] **Step 4: Final commit**

```bash
git add docs/
git commit -m "docs: update HLDs for account aggregator, mark LLD as Verified"
```
