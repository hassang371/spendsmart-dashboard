import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from ..excel_parser import parse_excel_transaction_file, _OLE2_MAGIC

# OLE2 magic prefix to simulate encrypted file content
_FAKE_ENCRYPTED = _OLE2_MAGIC + b"fake_encrypted_payload"


@pytest.fixture
def mock_excel_data():
    # Create a DataFrame that mimics the structure of the provided statement.xlsx
    # Rows 0-15 are junk
    data = {
        "Unnamed: 0": [None] * 20,
        "Unnamed: 1": [None] * 20,
        "Unnamed: 2": [None] * 20,
        "Unnamed: 3": [None] * 20,
        "Unnamed: 4": [None] * 20,
        "Unnamed: 5": [None] * 20,
    }
    df = pd.DataFrame(data)

    # Row 16 (index 16) is header
    df.iloc[16] = ["Date", "Details", "Ref No.", "Debit", "Credit", "Balance"]

    # Row 17 is data
    # Date, Details, Ref, Debit, Credit, Balance
    df.iloc[17] = [
        "28/04/2023",
        "TEST TRANSACTION",
        "REF123",
        100.0,
        None,
        2000.0,
    ]  # Debit (Withdrawal)
    df.iloc[18] = [
        "29/04/2023",
        "SALARY",
        "REF124",
        None,
        5000.0,
        7000.0,
    ]  # Credit (Deposit)

    return df


@patch("packages.ingestion_engine.excel_parser.msoffcrypto")
@patch("packages.ingestion_engine.excel_parser.pd.read_excel")
def test_parse_encrypted_excel(mock_read_excel, mock_msoffcrypto, mock_excel_data):
    # Prepare sliced dataframe for the second call (header=16)
    # The actual data is in row 17 (index 17 in raw, which is index 0 in sliced if header is 16)

    # Manually create the DF that read_excel WOULD return if header=16
    data_rows = [
        ["28/04/2023", "TEST TRANSACTION", "REF123", 100.0, None, 2000.0],
        ["29/04/2023", "SALARY", "REF124", None, 5000.0, 7000.0],
    ]
    columns = ["Date", "Details", "Ref No.", "Debit", "Credit", "Balance"]
    df_sliced = pd.DataFrame(data_rows, columns=columns)

    # Side effect: First call (header detection) returns raw, Second call returns sliced
    mock_read_excel.side_effect = [mock_excel_data, df_sliced]

    # Setup encryption mock
    mock_file = MagicMock()
    mock_msoffcrypto.OfficeFile.return_value = mock_file

    # Fake file content with OLE2 magic bytes (simulating encrypted .xlsx)
    file_content = _FAKE_ENCRYPTED
    password = "test_password"

    # Call the function
    df = parse_excel_transaction_file(file_content, password=password)

    # Assertions
    # 1. Check decryption happened
    mock_msoffcrypto.OfficeFile.assert_called()
    mock_file.load_key.assert_called_with(password=password)
    mock_file.decrypt.assert_called()

    # 2. Check Data Loading
    # We expect 2 rows of data (index 17 and 18 from original)
    assert len(df) == 2

    # 3. Check standardized columns (date, description, amount)
    assert "date" in df.columns
    assert "description" in df.columns
    assert "amount" in df.columns

    # 4. Check Values
    # Row 1: Debit 100 -> Amount -100
    assert df.iloc[0]["amount"] == -100.0
    assert df.iloc[0]["description"] == "TEST TRANSACTION"

    # Row 2: Credit 5000 -> Amount 5000
    assert df.iloc[1]["amount"] == 5000.0
    assert df.iloc[1]["description"] == "SALARY"


def test_encrypted_file_without_password_raises():
    """OLE2 file without password should immediately raise 'Password required'."""
    with pytest.raises(ValueError, match="Password required"):
        parse_excel_transaction_file(_FAKE_ENCRYPTED, password=None)


@patch("packages.ingestion_engine.excel_parser.pd.read_excel")
def test_plain_xlsx_skips_decryption(mock_read_excel):
    """Plain .xlsx (ZIP-based) should skip msoffcrypto entirely."""
    data_rows = [
        ["2023-04-28", "TEST TRANSACTION", 100.0, 0.0],
        ["2023-04-29", "SALARY", 0.0, 5000.0],
    ]
    raw_df = pd.DataFrame(
        {
            "Unnamed: 0": ["Date", "2023-04-28", "2023-04-29"],
            "Unnamed: 1": ["Details", "TEST TRANSACTION", "SALARY"],
            "Unnamed: 2": ["Debit", 100.0, None],
            "Unnamed: 3": ["Credit", None, 5000.0],
        }
    )
    sliced_df = pd.DataFrame(data_rows, columns=["Date", "Details", "Debit", "Credit"])
    mock_read_excel.side_effect = [raw_df, sliced_df]

    # ZIP magic bytes (PK header) — a real .xlsx starts with this
    plain_xlsx_bytes = b"PK\x03\x04" + b"\x00" * 100

    df = parse_excel_transaction_file(plain_xlsx_bytes, password=None)
    assert len(df) == 2
