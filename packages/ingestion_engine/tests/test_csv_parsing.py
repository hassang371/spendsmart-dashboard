from io import StringIO
from packages.ingestion_engine.import_transactions import parse_csv_content


def test_parse_csv_header_normalization():
    """
    Test that CSVs with different header names are normalized to standard columns:
    date, amount, merchant, description
    """
    csv_content = """Date,Transaction Date,Description,Amount,Debit
2026-02-12,2026-02-12,Starbucks,5.50,5.50"""

    # We simulate a file-like object
    df = parse_csv_content(StringIO(csv_content))

    assert "date" in df.columns
    assert "merchant" in df.columns
    assert "amount" in df.columns
    # Should resolve 'Description' -> 'merchant' if logic heuristics apply,
    # or 'Description' -> 'description' and we extract merchant later.
    # Let's assume standard 'description' field for now.


def test_parse_csv_sign_normalization():
    """
    Test that Debits are normalized to Negative values and Credits to Positive.
    """
    # Case 1: 'Debit' and 'Credit' columns
    csv_data = """Date,Description,Debit,Credit
2026-02-12,Salary,,5000.00
2026-02-13,Rent,2000.00,"""

    df = parse_csv_content(StringIO(csv_data))

    # Salary should be +5000.00
    salary_row = df[df["description"] == "Salary"].iloc[0]
    assert salary_row["amount"] == 5000.00

    # Rent should be -2000.00 (Expenses are negative in our ledger)
    rent_row = df[df["description"] == "Rent"].iloc[0]
    assert rent_row["amount"] == -2000.00


def test_parse_csv_amount_column():
    """
    Test single 'Amount' column where negatives are implicit or explicit with - sign.
    """
    csv_data = """Date,Description,Amount
2026-02-12,Coffee,-5.00
2026-02-13,Refund,10.00"""

    df = parse_csv_content(StringIO(csv_data))

    coffee_row = df[df["description"] == "Coffee"].iloc[0]
    assert coffee_row["amount"] == -5.00

    refund_row = df[df["description"] == "Refund"].iloc[0]
    assert refund_row["amount"] == 10.00


def test_parse_csv_payment_method_mapping():
    """
    Test that Google Pay CSV 'Payment method' column is mapped to 'method' in output.
    """
    csv_data = """"Time","Transaction ID","Description","Product","Payment method","Status","Amount"
"7 Feb 2026, 17:13",GPY.123,Music Premium,YouTube,Visa **** 3534,Complete,INR 299.00
"7 Feb 2026, 09:44",YPC.456,Cloud Storage,Google One,UPI: QR code,Complete,INR 129.00
"6 Feb 2026, 23:26",YPC.789,Play Pass,Google Play Apps,Axis Bank UPI,Complete,INR 149.00"""

    df = parse_csv_content(StringIO(csv_data))

    assert (
        "method" in df.columns
    ), "Expected 'method' column from 'Payment method' mapping"
    assert df.iloc[0]["method"] == "Visa **** 3534"
    assert df.iloc[1]["method"] == "UPI: QR code"
    assert df.iloc[2]["method"] == "Axis Bank UPI"


def test_parse_csv_status_passthrough():
    """
    Test that CSV 'Status' column is preserved in output as 'status'.
    """
    csv_data = """"Time","Description","Status","Amount"
"7 Feb 2026, 17:13",Music Premium,Complete,INR 299.00
"6 Feb 2026, 03:20",YouTube Premium,Refunded,INR 59.00
"6 Feb 2026, 02:10",Play Pass,Cancelled,INR 299.00"""

    df = parse_csv_content(StringIO(csv_data))

    assert "status" in df.columns, "Expected 'status' column to be preserved"
    assert df.iloc[0]["status"] == "Complete"
    assert df.iloc[1]["status"] == "Refunded"
    assert df.iloc[2]["status"] == "Cancelled"


def test_parse_file_csv_carries_method_and_status():
    """
    End-to-end test: parse_file for CSV returns method and status columns.
    """
    from packages.ingestion_engine.import_transactions import parse_file

    csv_bytes = b""""Time","Description","Product","Payment method","Status","Amount"
"7 Feb 2026, 17:13",Music Premium,YouTube,Visa **** 3534,Complete,INR 299.00
"6 Feb 2026, 03:20",YouTube Premium,YouTube,Visa **** 5315,Refunded,INR 59.00"""

    df = parse_file(csv_bytes, "Transactions.csv")

    assert "method" in df.columns, "parse_file should return 'method' column"
    assert "status" in df.columns, "parse_file should return 'status' column"
    assert df.iloc[0]["method"] == "Visa **** 3534"
    assert df.iloc[1]["status"] == "Refunded"
