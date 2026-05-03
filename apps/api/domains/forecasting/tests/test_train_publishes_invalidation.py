"""Verifies the worker publishes a cache-invalidation message AFTER
the ``training_jobs.status='completed'`` DB commit succeeds.

Refs: docs/rfcs/RFC-004-tft-inference-cache-architecture.md §4
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.worker.job_states import JobStatus


@pytest.fixture(autouse=True)
def fake_redis_url(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    yield


class FakeQuery:
    """A chainable query mock that records the .update payload it sees
    so the test can assert ordering between writes and publishes."""

    def __init__(self, recorder: list, table_name: str, seed_data=None):
        self._rec = recorder
        self._table = table_name
        self._seed_data = seed_data
        self._last_update_payload = None
        self._is_claim_filter = False

    def select(self, *args, **kwargs):
        return self

    def insert(self, *args, **kwargs):
        return self

    def delete(self, *args, **kwargs):
        return self

    def update(self, payload, *args, **kwargs):
        self._last_update_payload = payload
        # Record the completed-status write so the test can assert
        # ordering. JobStatus.COMPLETED is an enum; compare by value.
        status = payload.get("status") if isinstance(payload, dict) else None
        status_value = getattr(status, "value", status)
        if status_value == JobStatus.COMPLETED.value:
            self._rec.append("db_commit_completed")
        return self

    def eq(self, *args, **kwargs):
        # Track if the second eq is on status=PENDING (claim path).
        if args and args[0] == "status" and len(args) > 1:
            val = getattr(args[1], "value", args[1])
            if val == JobStatus.PENDING.value:
                self._is_claim_filter = True
        return self

    def limit(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def gte(self, *args, **kwargs):
        return self

    def execute(self):
        if self._seed_data is not None:
            return MagicMock(data=self._seed_data)
        # If this was a claim-filter update, return a truthy claim row.
        if self._is_claim_filter:
            return MagicMock(data=[{"id": "job-1"}])
        return MagicMock(data=[])


def test_publish_invalidation_fires_after_status_completed_commit():
    from apps.worker import main as worker_main

    call_order: list[str] = []
    pending_seed = [
        {
            "id": "job-1",
            "user_id": "user-1",
            "status": JobStatus.PENDING.value,
            "job_type": "forecasting",
            "celery_task_id": None,
        }
    ]
    seen_select_once = {"flag": False}

    def _table_factory(table_name: str):
        # The very first .table('training_jobs').select(...).eq(PENDING)
        # call needs to return the pending seed; subsequent updates need
        # the FakeQuery treatment.
        if not seen_select_once["flag"]:
            seen_select_once["flag"] = True
            return FakeQuery(call_order, table_name, seed_data=pending_seed)
        return FakeQuery(call_order, table_name)

    supabase = MagicMock()
    supabase.table.side_effect = _table_factory

    with (
        patch.object(worker_main, "train_model", return_value="train_complete"),
        patch("packages.forecasting.cache_invalidation.publish_invalidation_sync") as mock_publish,
        patch("redis.from_url") as mock_redis_from_url,
    ):
        mock_redis_from_url.return_value = MagicMock()

        def _publish_record(client, user_id, ts):
            call_order.append("pubsub_publish")
            return True

        mock_publish.side_effect = _publish_record

        result = worker_main.process_next_job(supabase)
        assert result is True

    # The publish must have been called exactly once and AFTER the
    # COMPLETED-status DB commit.
    mock_publish.assert_called_once()
    assert "db_commit_completed" in call_order, call_order
    assert "pubsub_publish" in call_order, call_order
    assert call_order.index("db_commit_completed") < call_order.index(
        "pubsub_publish"
    ), f"publish must happen after DB commit, got {call_order}"

    args, _kwargs = mock_publish.call_args
    # publish_invalidation_sync(redis_client, user_id, completed_at)
    assert args[1] == "user-1"
    # 3rd arg = ISO string with "T" separator.
    assert isinstance(args[2], str) and "T" in args[2]
