from apps.api.domains.ingestion.router import _build_transaction_row


def test_merchant_name_extracted_from_description_when_empty():
    row = {
        "date": "2026-01-01",
        "amount": -210.0,
        "description": "YouTube Premium Individual",
        "merchant": "",
        "payment_method": "",
        "currency": "INR",
        "status": "completed",
    }
    result = _build_transaction_row(row, "user-1", "fp123")
    # v2 cleaner preserves richer merchant name when not a known pattern
    assert "YouTube" in result["merchant_name"]
    assert result["merchant_name"] != ""


def test_payment_method_inferred_when_empty():
    row = {
        "date": "2026-01-01",
        "amount": -99.0,
        "description": "UPI-SWIGGY-pay@okaxis",
        "merchant": "",
        "payment_method": "",
        "currency": "INR",
        "status": "completed",
    }
    result = _build_transaction_row(row, "user-1", "fp456")
    assert result["payment_method"] == "UPI"


def test_payment_method_preserved_when_csv_provides_it():
    row = {
        "date": "2026-01-01",
        "amount": -500.0,
        "description": "some transaction",
        "merchant": "Some Store",
        "payment_method": "Card",
        "currency": "INR",
        "status": "completed",
    }
    result = _build_transaction_row(row, "user-1", "fp789")
    assert result["payment_method"] == "Card"


def test_google_play_gets_other_payment_method():
    # "Play Pass Monthly" has no UPI/NEFT/card indicator — payment method cannot be inferred
    row = {
        "date": "2026-01-01",
        "amount": -129.0,
        "description": "Play Pass Monthly",
        "merchant": "",
        "payment_method": "",
        "currency": "INR",
        "status": "completed",
    }
    result = _build_transaction_row(row, "user-1", "fp999")
    assert result["payment_method"] == "Other"
