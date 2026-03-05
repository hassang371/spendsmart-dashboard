import pytest
import pandas as pd
from unittest.mock import patch, MagicMock, mock_open
from packages.categorization.data_loader import BankStatementParser

# Mock data simulating the Excel file structure we inspected
# Header at row 16 (index 16), actual data starts below
MOCK_EXCEL_DATA = {
    "Unnamed: 0": ["Header"] + ["28/04/2023", "03/06/2023"],
    "Unnamed: 1": ["Details"]
    + [
        "CASH DEPOSIT SELF\n AT 04413 PBB NELLORE",
        "ATM WDL   ATM CASH 1957  SP\n  OFFICE DARGAMITTA, NELLORE",
    ],
    "Unnamed: 2": ["Ref No"] + [None, None],
    "Unnamed: 3": ["Debit"] + [None, 500.00],
    "Unnamed: 4": ["Credit"] + [2000.00, None],
    "Unnamed: 5": ["Balance"] + [2000.00, 1500.00],
}


@pytest.fixture
def mock_excel_file():
    # Create a DataFrame that mimics the "skiprows" logic
    # The parser should look for the header 'Details' in 'Unnamed: 1'
    df = pd.DataFrame(MOCK_EXCEL_DATA)
    return df


def test_parser_initialization():
    parser = BankStatementParser("dummy.xlsx", password="password")
    assert parser.file_path == "dummy.xlsx"
    assert parser.password == "password"


@patch("builtins.open", new_callable=mock_open)
@patch("packages.categorization.data_loader.msoffcrypto.OfficeFile")
@patch("packages.categorization.data_loader.pd.read_excel")
def test_parse_valid_excel(mock_read_excel, mock_office_file_cls, mock_file_open):
    # Mocking the decryption process
    mock_file_instance = MagicMock()
    mock_office_file_cls.return_value = mock_file_instance

    # Create the raw dataframe (with junk rows)
    df_raw = pd.DataFrame(MOCK_EXCEL_DATA)
    junk_rows = pd.DataFrame([["Junk"] * 6] * 16, columns=df_raw.columns)
    full_df = pd.concat([junk_rows, df_raw]).reset_index(drop=True)

    # Create the clean dataframe (what read_excel returns after finding header)
    clean_df = df_raw.copy()
    clean_df.columns = clean_df.iloc[0]  # Promote header
    clean_df = clean_df[1:].reset_index(drop=True)  # Drop header row
    clean_df = clean_df.rename(
        columns={
            "Header": "Date",
            "Details": "Details",
            "Ref No": "Ref No",
            "Debit": "Debit",
            "Credit": "Credit",
            "Balance": "Balance",
        }
    )  # Map columns as parser expects

    # Mock read_excel side effects
    # 1st call: read raw (to find header)
    # 2nd call: read from header (to get data)
    mock_read_excel.side_effect = [full_df, clean_df]

    parser = BankStatementParser("dummy.xlsx", password="password")
    df = parser.parse()

    # Assertions
    assert len(df) == 2
    assert "Details" in df.columns
    assert "Amount" in df.columns

    # Check amount calculation (Credit - Debit)
    # Row 1: Credit 2000, Debit NaN -> Amount 2000
    assert df.iloc[0]["Amount"] == 2000.0
    # Row 2: Credit NaN, Debit 500 -> Amount -500
    assert df.iloc[1]["Amount"] == -500.0

    # Check description cleaning
    # Should remove newlines and extra spaces
    cleaned = df.iloc[0]["Cleaned_Details"]
    assert "CASH DEPOSIT SELF" in cleaned
    assert "AT 04413 PBB NELLORE" not in cleaned
    assert "\n" not in cleaned


def test_clean_details_logic():
    parser = BankStatementParser("dummy.xlsx")

    raw_text = "POS ATM PURCH   OTHPG 3155010693\n 17Pho*PHONEPE RECHARGE  BANGALORE"
    cleaned = parser.clean_details(raw_text)

    assert "POS ATM PURCH" not in cleaned
    assert "PHONEPE RECHARGE" in cleaned
    assert "BANGALORE" in cleaned
    assert "3155010693" not in cleaned  # specific ID removal


def test_get_cleaning_diff():
    # Test the new method for inspection
    parser = BankStatementParser("dummy.xlsx", password="password")
    # Mock dataframe manually since we are not parsing real file
    parser.df = pd.DataFrame(
        {"Details": ["POS txn", "ATM wdl"], "Cleaned_Details": ["txn", "wdl"]}
    )

    # This method doesn't exist yet, so it should fail (AttributeError)
    diff = parser.get_cleaning_diff()

    assert len(diff) == 2
    assert diff[0] == ("POS txn", "txn")
    assert diff[1] == ("ATM wdl", "wdl")
