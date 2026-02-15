from io import StringIO
from typing import List, Dict, Any
from packages.ingestion_engine.import_transactions import (
    parse_csv_content,
    generate_fingerprint,
)

from packages.ingestion_engine.merchant_extractor import MerchantExtractor


def process_file_logic(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Core logic for checking a file upload.
    1. Parses CSV from bytes.
    2. Generates fingerprints.
    3. Returns list of records ready for DB insertion.
    """
    # Decode bytes to string
    try:
        csv_text = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        # Fallback to latin-1? Or fail? Let's try latin-1 for banking legacy systems
        csv_text = file_bytes.decode("latin-1")

    # Parse Dataframe
    df = parse_csv_content(StringIO(csv_text))

    # Drop rows with invalid dates or amounts before processing
    df = df.dropna(subset=["date", "amount"])
    df = df[df["date"] != "NaT"]  # Remove NaT (Not a Time) values

    extractor = MerchantExtractor()

    results = []
    for _, row in df.iterrows():
        # Clean merchant
        raw_merchant = str(row.get("merchant", ""))
        raw_desc = str(row.get("description", ""))

        # Prefer existing merchant column if valid, but clean it.
        # If empty, use description.
        source = raw_merchant if len(raw_merchant) > 2 else raw_desc
        cleaned_merchant = extractor.extract(source)

        # Standardize for fingerprinting
        record = {
            "date": row["date"],
            "amount": float(row["amount"]),
            "description": raw_desc,
            "merchant": cleaned_merchant,
        }

        # Generate ID
        record["fingerprint"] = generate_fingerprint(
            record["date"], record["amount"], cleaned_merchant or raw_desc
        )

        results.append(record)

    return results
