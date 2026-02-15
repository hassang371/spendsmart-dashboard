import pandas as pd

# We will move the logic to a helper function, so we import it here.
# Since it doesn't exist yet, we will define the test first (TDD).
# We expect to create a function `prepare_transaction_payload` in `apps.api.routers.training`
# or a new utility module. For now, let's assume it's in `apps.api.routers.training`.

from apps.api.routers.training import prepare_transaction_payload


def test_prepare_transaction_payload_structure():
    """
    Verifies that the payload construction correctly:
    1. Extracts standard fields (date, amount, description, merchant)
    2. Extracts structured fields (method, entity, location, ref) into 'raw_data'
    3. Handles missing structured fields gracefully
    """

    # Mock Dataframe Row
    # Simulating what BankStatementParser returns
    data = {
        "date": [pd.Timestamp("2023-06-07")],
        "amount": [-162.0],
        "description": ["POS 1234 SWIGGY BANGALORE"],
        "merchant": ["Swiggy"],
        # Structured Fields
        "method": ["POS"],
        "entity": ["Swiggy"],
        "location": ["BANGALORE"],
        "ref": ["3157044560"],
        "type": ["DEBIT"],
        "meta": [{"bank": "SBI"}],  # JSON object
    }
    df = pd.DataFrame(data)
    row = df.iloc[0]

    user_id = "test-user-id"

    # Execute
    payload = prepare_transaction_payload(row, user_id)

    # Assertions
    assert payload["user_id"] == user_id
    assert payload["amount"] == -162.0
    assert payload["merchant_name"] == "Swiggy"
    assert payload["transaction_date"] == "2023-06-07"

    # Check raw_data presence and content
    assert "raw_data" in payload
    raw_data = payload["raw_data"]

    assert raw_data["method"] == "POS"
    assert raw_data["entity"] == "Swiggy"
    assert raw_data["location"] == "BANGALORE"
    assert raw_data["ref"] == "3157044560"
    assert raw_data["meta"] == {"bank": "SBI"}


def test_prepare_transaction_payload_missing_fields():
    """
    Verifies behavior when structured columns are missing (backward compatibility)
    """
    data = {
        "date": [pd.Timestamp("2023-06-07")],
        "amount": [-100.0],
        "description": ["CASH WDL"],
        "merchant": ["CASH"],
    }
    # Note: method, entity, etc. are missing
    df = pd.DataFrame(data)
    row = df.iloc[0]

    user_id = "test-user-id-2"

    payload = prepare_transaction_payload(row, user_id)

    assert payload["amount"] == -100.0
    assert "raw_data" in payload
    # Should probably be empty strings or None, depending on implementation
    # Let's assert keys exist but are empty/None for safety
    assert payload["raw_data"].get("method") in [None, ""]
