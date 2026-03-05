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


def generate_fingerprint(
    iso_date: str, amount: float, merchant: str, salt: str = ""
) -> str:
    """
    Generates a unique SHA256 fingerprint for a transaction.
    Format: SHA256({ISO_Date_Sec}|{Amount_Float}|{Merchant_Normalized}|{salt})
    """
    normalized_merchant = normalize_merchant(merchant)
    raw_string = f"{iso_date}|{amount}|{normalized_merchant}|{salt}"
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
            "timestamp",
            "transaction_date",
            "transaction date",
            "posting date",
            "trans date",
            "posting_date",
            "trans_date",
        ],
        "description": [
            "description",
            "desc",
            "original description",
            "memo",
            "merchant_category", # Used as fallback for description if real desc is missing
        ],
        "merchant": ["merchant", "merchant name", "payee"],
        "amount": ["amount", "value", "amt", "amount (inr)"],
        "debit": ["debit", "withdrawal", "dr"],
        "credit": ["credit", "deposit", "cr"],
        "status": ["status", "state", "transaction status", "transaction_status"],
        "method": ["payment method", "payment_method", "mode", "payment mode", "transaction type"],
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


def _parse_pdf(file_content: bytes) -> pd.DataFrame:
    """Extract transaction table from a PDF bank statement using pdfplumber.

    Scans every page for the largest table and concatenates them. Normalises
    the result with _normalize_dataframe so downstream code gets standard columns.
    """
    import io
    import pdfplumber

    all_rows: list[list] = []
    header: list | None = None

    with pdfplumber.open(io.BytesIO(file_content)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if not tables:
                continue
            # Pick the widest table on the page
            table = max(tables, key=lambda t: len(t[0]) if t else 0)
            if not table:
                continue
            if header is None:
                # First non-empty row is the header
                header = [str(c).strip() if c else "" for c in table[0]]
                all_rows.extend(table[1:])
            else:
                # Subsequent pages: skip row if it matches the header (repeated header)
                for row in table:
                    row_strs = [str(c).strip() if c else "" for c in row]
                    if row_strs != header:
                        all_rows.append(row)

    if not all_rows or header is None:
        raise ValueError("No table found in PDF. Ensure it is a bank statement with tabular data.")

    df = pd.DataFrame(all_rows, columns=header)
    # Drop fully-empty rows
    df = df.dropna(how="all")
    df = df[df.apply(lambda r: r.astype(str).str.strip().ne("").any(), axis=1)]
    return _normalize_dataframe(df)


def parse_file(
    file_content: bytes, filename: str, password: str = None
) -> pd.DataFrame:
    """
    Parses a transaction file (CSV, Excel, JSON, TSV, PDF) based on extension/content.
    """
    import io
    import json as _json

    filename_lower = filename.lower()

    if filename_lower.endswith(".pdf"):
        return _parse_pdf(file_content)

    if (
        filename_lower.endswith(".xlsx")
        or filename_lower.endswith(".xls")
        or filename_lower.endswith(".xlsm")
    ):
        pass

        # Use v2 excel parser
        from packages.ingestion_engine.excel_parser import parse_excel_transaction_file

        df = parse_excel_transaction_file(file_content, password=password)

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

    # Generate / clean merchant for ALL file types (including xlsx)
    from .merchant_extractor import MerchantExtractor

    extractor = MerchantExtractor()

    if "merchant" not in df.columns and "description" in df.columns:
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
