# apps/api/domains/ingestion/tests/test_account_id.py
"""Test ingestion account_id wiring."""

from unittest.mock import MagicMock

import pytest

from apps.api.domains.ingestion.router import _build_transaction_row, _rpc_insert_batch


def test_build_transaction_row_includes_account_id():
    row = {"date": "2026-03-10", "amount": -100.0, "description": "Test"}
    result = _build_transaction_row(row, "user-1", "fp-123", "acc-1")
    assert result["account_id"] == "acc-1"


def test_rpc_insert_batch_passes_account_id():
    client = MagicMock()
    client.rpc.return_value.execute.return_value = MagicMock(data=[{"inserted_count": 1, "skipped_count": 0}])
    _rpc_insert_batch(client, "user-1", "acc-1", [{"fingerprint": "fp-1"}])
    params = client.rpc.call_args[0][1]
    assert params["p_account_id"] == "acc-1"
