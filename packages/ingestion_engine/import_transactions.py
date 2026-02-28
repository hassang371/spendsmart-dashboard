import hashlib
import pandas as pd
from typing import IO


def normalize_merchant(merchant: str) -> str:
    """
    Normalizes merchant string by uppercasing and stripping whitespace.
    """
    if not merchant or pd.isna(merchant):
        return ""
    return str(merchant).strip().upper()


def generate_fingerprint(iso_date: str, amount: float, merchant: str) -> str:
    """
    Generates a unique SHA256 fingerprint for a transaction.
    Format: SHA256({ISO_Date_Sec}|{Amount_Float}|{Merchant_Normalized})
    """
    normalized_merchant = normalize_merchant(merchant)
    raw_string = f"{iso_date}|{amount}|{normalized_merchant}"
    return hashlib.sha256(raw_string.encode("utf-8")).hexdigest()


def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalizes a DataFrame with transaction data.
    Applies column mapping, amount cleaning, date standardization.
    Used by all parsers (CSV, JSON, TSV) for consistent output.
    """
    # 1. Normalize Header Names
    df.columns = [str(c).strip().lower() for c in df.columns]

    # 2. Map Columns intelligently (Avoid duplicates)
    # Define priority lists for each target column
    column_priorities = {
        "date": [
            "date",
            "time",
            "transaction_date",
            "transaction date",
            "posting date",
            "trans date",
            "posting_date",
            "trans_date",
        ],
        "description": ["description", "desc", "original description", "memo"],
        "merchant": ["merchant", "merchant name", "payee"],
        "amount": ["amount", "value", "amt"],
        "debit": ["debit", "withdrawal", "dr"],
        "credit": ["credit", "deposit", "cr"],
        "status": ["status", "state", "transaction status"],
        "method": ["payment method", "payment_method", "mode", "payment mode"],
        "product": ["product", "item", "product name"],
    }

    # Identify renaming map based on what exists
    rename_map = {}
    found_cols = set()

    for target, candidates in column_priorities.items():
        for candidate in candidates:
            if candidate in df.columns and candidate not in found_cols:
                rename_map[candidate] = target
                found_cols.add(candidate)
                break  # Take the first match for this target

    # Apply renaming
    df.rename(columns=rename_map, inplace=True)

    # 3. Handle Amount / Debit / Credit Logic
    # Helper: strip currency prefixes like "INR 299.00", "USD 50", "$100"
    def _clean_currency(series: pd.Series) -> pd.Series:
        return series.astype(str).str.replace(r"^[A-Za-z₹$€£¥]+\s*", "", regex=True)

    if "debit" in df.columns and "credit" in df.columns:
        # Fill NaNs with 0
        df["debit"] = pd.to_numeric(
            _clean_currency(df["debit"]), errors="coerce"
        ).fillna(0)
        df["credit"] = pd.to_numeric(
            _clean_currency(df["credit"]), errors="coerce"
        ).fillna(0)

        # Calculate amount
        df["amount"] = df["credit"] - df["debit"]

    elif "amount" in df.columns:
        # Clean amount column (strip currency prefixes)
        df["amount"] = pd.to_numeric(
            _clean_currency(df["amount"]), errors="coerce"
        ).fillna(0)
    else:
        # Logical error or empty logic, but let's return what we have
        if "amount" not in df.columns:
            df["amount"] = 0.0

    # 3b. Status-based sign logic (Google Pay/Play exports)
    # If a 'status' column exists, use it to determine the sign of each amount:
    #   - Refunded → positive (money returned = income/credit)
    #   - Cancelled → zero (no money moved)
    #   - Complete / other → negative (money spent = expense)
    if "status" in df.columns:
        status_lower = df["status"].astype(str).str.strip().str.lower()
        # Only apply if amounts are all-positive (expense-style export)
        if (df["amount"][df["amount"] != 0] >= 0).all():
            df.loc[status_lower == "cancelled", "amount"] = 0.0
            # Refunded stays positive (credit)
            # Everything else (complete, etc.) becomes negative (expense)
            expense_mask = ~status_lower.isin(["refunded", "cancelled"])
            df.loc[expense_mask, "amount"] = -df.loc[expense_mask, "amount"].abs()

    # 4. Standardize Date
    if "date" in df.columns:
        # Coerce errors to NaT, then drop or handle? For now, standard behavior.
        df["date"] = pd.to_datetime(
            df["date"], dayfirst=True, errors="coerce"
        ).dt.strftime("%Y-%m-%d")

    # 5. Ensure merchant column exists
    if "merchant" not in df.columns and "description" in df.columns:
        df["merchant"] = df["description"]
    elif "merchant" not in df.columns:
        df["merchant"] = ""

    # Final cleanup: Select only standard columns if they exist
    standard_cols = ["date", "amount", "description", "merchant", "status", "method"]
    result_cols = [c for c in standard_cols if c in df.columns]

    return df[result_cols]


def parse_csv_content(file_content: IO) -> pd.DataFrame:
    """
    Parses a CSV file object into a normalized DataFrame.
    Standard Columns: date, amount, description, merchant
    """
    df = pd.read_csv(file_content)
    return _normalize_dataframe(df)


def parse_file(
    file_content: bytes, filename: str, password: str = None
) -> pd.DataFrame:
    """
    Parses a transaction file (CSV, Excel, JSON, TSV) based on extension/content.
    """
    import io
    import json as _json

    filename_lower = filename.lower()

    if (
        filename_lower.endswith(".xlsx")
        or filename_lower.endswith(".xls")
        or filename_lower.endswith(".xlsm")
    ):
        # Use new BankStatementParser
        from packages.categorization.data_loader import BankStatementParser

        parser = BankStatementParser(file_content, password=password)
        try:
            df = parser.parse()
        except Exception as e:
            # Fallback or re-raise
            # If password error, re-raise specifically
            if "Decryption failed" in str(e) or "Password" in str(e):
                raise ValueError("Invalid password")
            raise e

        # Normalize columns to match ingestion expectation
        # Parser returns: Date, Details, Amount, Cleaned_Details, method, entity, ref, location, type, meta
        rename_map = {
            "Date": "date",
            "Details": "description",
            "Amount": "amount",
            "Cleaned_Details": "merchant",  # Use our cleaned entity as merchant
        }
        df = df.rename(columns=rename_map)

        # Standardize dates to ISO format (YYYY-MM-DD) for PostgreSQL
        if "date" in df.columns:
            df["date"] = pd.to_datetime(
                df["date"], dayfirst=True, errors="coerce"
            ).dt.strftime("%Y-%m-%d")

        # Ensure we have the standard columns
        for col in ["date", "description", "amount", "merchant"]:
            if col not in df.columns:
                df[col] = "" if col != "amount" else 0.0

    elif filename_lower.endswith(".json"):
        raw = _json.loads(file_content.decode("utf-8"))
        rows = raw if isinstance(raw, list) else raw.get("transactions", [])
        df = pd.DataFrame(rows)
        df = _normalize_dataframe(df)  # Apply shared normalization
    elif filename_lower.endswith(".tsv"):
        text_stream = io.StringIO(file_content.decode("utf-8"))
        df = pd.read_csv(text_stream, sep="\t")
        df = _normalize_dataframe(df)  # Apply shared normalization
    else:
        # Default: treat as CSV
        text_stream = io.StringIO(file_content.decode("utf-8"))
        df = parse_csv_content(text_stream)

    # Generate merchant if missing (Common post-processing)
    # Only if we didn't use BankStatementParser (which already generates it)
    if not filename_lower.endswith(".xlsx") and not filename_lower.endswith(".xls"):
        from .merchant_extractor import MerchantExtractor

        extractor = MerchantExtractor()

        if "merchant" not in df.columns and "description" in df.columns:
            # Extract clean merchant from description
            df["merchant"] = df["description"].apply(extractor.extract)
        elif "merchant" not in df.columns:
            df["merchant"] = ""
        else:
            # Even if merchant column exists, clean it if it looks like raw description
            df["merchant"] = df["merchant"].astype(str).apply(extractor.extract)

    # Standardize result columns + Extended columns
    standard_cols = ["date", "amount", "description", "merchant"]
    extended_cols = ["method", "entity", "ref", "location", "type", "meta", "status"]

    # Ensure extended columns exist (fill empty if simple CSV)
    for col in extended_cols:
        if col not in df.columns:
            df[col] = ""

    # Return all columns
    final_cols = [c for c in standard_cols + extended_cols if c in df.columns]
    return df[final_cols]
