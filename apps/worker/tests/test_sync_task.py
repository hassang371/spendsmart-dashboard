# apps/worker/tests/test_sync_task.py
"""Tests for the daily auto-sync task.

TDD: These tests define the expected behavior of sync_task.run_auto_sync()
before the implementation exists.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.worker.sync_task import run_auto_sync


class TestRunAutoSync:
    """Tests for run_auto_sync(supabase) — daily sync of active AA accounts."""

    def _make_supabase(self, accounts: list[dict]) -> MagicMock:
        """Build a mock Supabase client that returns the given accounts list."""
        client = MagicMock()
        select_chain = MagicMock()
        select_chain.execute.return_value = MagicMock(data=accounts)
        client.table.return_value.select.return_value.eq.return_value.eq.return_value = select_chain
        return client

    def _patch_provider(self):
        """Context manager that replaces _get_setu_provider with a MagicMock."""
        return patch("apps.worker.sync_task._get_setu_provider", return_value=MagicMock())

    @pytest.mark.asyncio
    async def test_no_active_accounts_does_nothing(self):
        """If no accounts have consent_status=active, sync is not called."""
        supabase = self._make_supabase(accounts=[])

        with (
            self._patch_provider(),
            patch("apps.worker.sync_task.service.sync_account", new_callable=AsyncMock) as mock_sync,
        ):
            result = await run_auto_sync(supabase)

        mock_sync.assert_not_called()
        assert result["synced"] == 0
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_stale_account_is_synced(self):
        """An active account with last_synced_at > 24 h ago triggers sync."""
        stale_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        account = {
            "id": "acc-1",
            "user_id": "user-1",
            "consent_id": "consent-1",
            "last_synced_at": stale_ts,
        }
        supabase = self._make_supabase(accounts=[account])

        with (
            self._patch_provider(),
            patch("apps.worker.sync_task.service.sync_account", new_callable=AsyncMock) as mock_sync,
        ):
            mock_sync.return_value = {"inserted": 5, "skipped_duplicates": 0}
            result = await run_auto_sync(supabase)

        mock_sync.assert_called_once()
        assert result["synced"] == 1
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_recently_synced_account_is_skipped(self):
        """An active account synced < 24 h ago is NOT re-synced."""
        fresh_ts = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        account = {
            "id": "acc-2",
            "user_id": "user-2",
            "consent_id": "consent-2",
            "last_synced_at": fresh_ts,
        }
        supabase = self._make_supabase(accounts=[account])

        with (
            self._patch_provider(),
            patch("apps.worker.sync_task.service.sync_account", new_callable=AsyncMock) as mock_sync,
        ):
            result = await run_auto_sync(supabase)

        mock_sync.assert_not_called()
        assert result["synced"] == 0
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_never_synced_account_is_synced(self):
        """An active account with last_synced_at=None (never synced) is synced."""
        account = {
            "id": "acc-3",
            "user_id": "user-3",
            "consent_id": "consent-3",
            "last_synced_at": None,
        }
        supabase = self._make_supabase(accounts=[account])

        with (
            self._patch_provider(),
            patch("apps.worker.sync_task.service.sync_account", new_callable=AsyncMock) as mock_sync,
        ):
            mock_sync.return_value = {"inserted": 10, "skipped_duplicates": 2}
            result = await run_auto_sync(supabase)

        mock_sync.assert_called_once()
        assert result["synced"] == 1
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_sync_error_is_counted_not_raised(self):
        """If sync raises, the error is counted but other accounts continue."""
        stale_ts = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        accounts = [
            {"id": "acc-4", "user_id": "u", "consent_id": "c1", "last_synced_at": stale_ts},
            {"id": "acc-5", "user_id": "u", "consent_id": "c2", "last_synced_at": stale_ts},
        ]
        supabase = self._make_supabase(accounts=accounts)

        call_count = 0

        async def _sync_side_effect(client, account_id, provider):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Setu timeout")
            return {"inserted": 3, "skipped_duplicates": 0}

        with self._patch_provider(), patch("apps.worker.sync_task.service.sync_account", side_effect=_sync_side_effect):
            result = await run_auto_sync(supabase)

        assert result["synced"] == 1
        assert result["errors"] == 1
