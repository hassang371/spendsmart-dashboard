import pandas as pd
import msoffcrypto
import io
import logging

logger = logging.getLogger(__name__)

# OLE2 Compound Document magic bytes — encrypted Office files use this container
_OLE2_MAGIC = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"


def _is_ole2(file_content: bytes) -> bool:
    """Check if file starts with the OLE2 magic bytes (indicates encryption wrapper)."""
    return file_content[:8] == _OLE2_MAGIC


def parse_excel_transaction_file(
    file_content: bytes, password: str = None
) -> pd.DataFrame:
    """
    Parses an encrypted (or unencrypted) Excel file into a standardized DataFrame.
    Returns columns: date, description, amount.
    """
    if _is_ole2(file_content):
        # File is in OLE2 format — either a legacy .xls or an encrypted .xlsx
        if not password:
            raise ValueError("Password required")

        decrypted_workbook = io.BytesIO()
        try:
            with io.BytesIO(file_content) as f:
                office_file = msoffcrypto.OfficeFile(f)
                office_file.load_key(password=password)
                office_file.decrypt(decrypted_workbook)
        except Exception as e:
            msg = str(e).lower()
            if "password" in msg or "decrypt" in msg or "key" in msg:
                raise ValueError("Invalid password")
            raise ValueError(f"Failed to decrypt file: {e}")
    else:
        # Plain .xlsx (ZIP-based OOXML) — no decryption needed
        decrypted_workbook = io.BytesIO(file_content)

    # Read Excel, finding header
    # We read first 20 rows to find header
    # Header signature: must contain 'Date' and ('Details' or 'Description') and ('Debit' or 'Withdrawal')

    # Read raw to find header
    decrypted_workbook.seek(0)
    df_raw = pd.read_excel(decrypted_workbook, header=None, nrows=30, engine="openpyxl")

    header_row_idx = -1
    for i, row in df_raw.iterrows():
        row_values = [str(x).lower() for x in row.values]
        if "date" in row_values and (
            "details" in row_values or "description" in row_values
        ):
            header_row_idx = i
            break

    if header_row_idx == -1:
        raise ValueError("Could not find valid header row in Excel file")

    # Read actual data
    decrypted_workbook.seek(0)
    df = pd.read_excel(
        decrypted_workbook, header=header_row_idx, engine="openpyxl", dtype=object
    )

    # Normalize Columns
    df.columns = [str(c).strip().lower() for c in df.columns]

    # Ensure required columns map
    # We expect: date, details, debit, credit
    # Rename to: date, description, debit, credit

    rename_map = {}
    for col in df.columns:
        if "date" in col:
            rename_map[col] = "date"
        elif "detail" in col or "description" in col or "particulars" in col:
            rename_map[col] = "description"
        elif "debit" in col:
            rename_map[col] = "debit"
        elif "credit" in col:
            rename_map[col] = "credit"
        elif "balance" in col:
            rename_map[col] = "balance"

    df.rename(columns=rename_map, inplace=True)

    # Calculate Amount
    # Amount = Credit (Positive) - Debit (Negative)
    # Fill NaN with 0

    if "credit" not in df.columns:
        df["credit"] = 0.0
    if "debit" not in df.columns:
        df["debit"] = 0.0

    df["credit"] = pd.to_numeric(df["credit"], errors="coerce").fillna(0.0)
    df["debit"] = pd.to_numeric(df["debit"], errors="coerce").fillna(0.0)

    # Create 'amount' column
    # If Debit is positive in the file (usual convention), we subtract it.
    df["amount"] = df["credit"] - df["debit"]

    # Filter empty rows (no date)
    df = df.dropna(subset=["date"])

    # Parse Date
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["date"])

    # Select final columns
    final_df = df[["date", "description", "amount"]].copy()

    return final_df
