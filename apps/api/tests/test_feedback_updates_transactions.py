"""Regression: POST /categorization/feedback must set is_manual=True on transactions.

Bug 4: feedback endpoint only wrote to training_corrections. The training
pipeline reads transactions WHERE is_manual=True — corrections were ignored.
"""

import inspect
from unittest.mock import MagicMock, patch


def test_feedback_handler_updates_transactions():
    """submit_feedback must update the transactions table after storing corrections."""
    from apps.api.domains.categorization.router import submit_feedback

    source = inspect.getsource(submit_feedback)
    assert (
        '"transactions"' in source or "'transactions'" in source
    ), "submit_feedback must update the 'transactions' table to set is_manual=True."
    assert "is_manual" in source, "submit_feedback must set is_manual=True on matching transactions."


def test_feedback_calls_transactions_update_for_each_correction():
    """One transactions.update() call is made per correction description."""
    import asyncio

    from apps.api.domains.categorization.router import submit_feedback
    from apps.api.domains.categorization.schemas import FeedbackRequest

    client_mock = MagicMock()
    # training_corrections insert
    client_mock.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
    # transactions update chain: .update().eq().eq().execute()
    update_chain = MagicMock()
    client_mock.table.return_value.update.return_value = update_chain
    update_chain.eq.return_value = update_chain
    update_chain.execute.return_value = MagicMock(data=[])

    req = FeedbackRequest(corrections={"Swiggy order": "Food", "Uber ride": "Transport"})
    # Call the handler directly — user_id and client injected as kwargs (bypasses Depends)
    asyncio.run(submit_feedback(req, user_id="uid-1", client=client_mock))

    # One update call per correction (check transactions table was called)
    update_calls = [c for c in client_mock.table.call_args_list if c.args and c.args[0] == "transactions"]
    assert len(update_calls) >= 2, f"Expected 2 transaction update calls, got {len(update_calls)}"
    assert (
        update_chain.execute.call_count >= 2
    ), f"Expected at least 2 .execute() calls on transactions update chain, got {update_chain.execute.call_count}"


def test_feedback_calls_transactions_update_for_list_shaped_corrections():
    """One transactions.update() call is made per description in a list-valued FeedbackRequest."""
    import asyncio

    from apps.api.domains.categorization.router import submit_feedback
    from apps.api.domains.categorization.schemas import FeedbackRequest

    client_mock = MagicMock()
    # training_corrections insert
    client_mock.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
    # transactions update chain: .update().eq().eq().execute()
    update_chain = MagicMock()
    client_mock.table.return_value.update.return_value = update_chain
    update_chain.eq.return_value = update_chain
    update_chain.execute.return_value = MagicMock(data=[])

    # List-valued shape: category → [description1, description2]
    req = FeedbackRequest(corrections={"Food": ["Swiggy order", "Zomato order"]})
    asyncio.run(submit_feedback(req, user_id="uid-1", client=client_mock))

    # One update call per description in the list (2 descriptions → 2 calls)
    update_calls = [c for c in client_mock.table.call_args_list if c.args and c.args[0] == "transactions"]
    assert len(update_calls) >= 2, f"Expected 2 transaction update calls, got {len(update_calls)}"
    assert (
        update_chain.execute.call_count >= 2
    ), f"Expected at least 2 .execute() calls on transactions update chain, got {update_chain.execute.call_count}"
