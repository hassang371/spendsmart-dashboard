import os
import sys
import argparse
import math
import hashlib
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv

# Load env
load_dotenv()

def get_env_value(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


# Setup Supabase (supports both legacy and dashboard env naming)
url = get_env_value("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL")
key = get_env_value(
    "SUPABASE_SERVICE_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_KEY",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY",
)

if not url or not key:
    print(
        "❌ Missing Supabase env vars. Set SUPABASE_URL/NEXT_PUBLIC_SUPABASE_URL and "
        "SUPABASE_SERVICE_KEY/SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY.",
    )
    sys.exit(1)

supabase: Client = create_client(url, key)

def ingest_file(file_path: str, user_id: str):
    print(f"📂 Reading file: {file_path}")
    
    try:
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
        elif file_path.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file_path)
        else:
            raise ValueError("Unsupported file format. Use CSV or Excel.")
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return

    # Normalize Headers (Basic)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    print(f"   Columns found: {list(df.columns)}")

    # Minimal validation/mapping
    required = ['date', 'amount', 'description']
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"❌ Missing required columns: {missing}")
        return

    def sanitize_value(v):
        """Convert pandas/numpy types to JSON-safe Python types."""
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        if isinstance(v, pd.Timestamp):
            return v.isoformat()
        if hasattr(v, 'item'):  # numpy scalar
            return v.item()
        return v

    records = []
    for _, row in df.iterrows():
        try:
            # Parse Amount
            amt = float(str(row['amount']).replace(',', '').replace('₹', '').replace('$', ''))

            # Type handling (if exists)
            txn_type = str(row.get('type', '') or '').lower()
            if txn_type == 'debit' and amt > 0:
                amt = -amt

            parsed_date = pd.to_datetime(str(row['date']))
            iso_date = parsed_date.to_pydatetime().isoformat()
            
            # Deterministic fingerprint using key fields to prevent duplicate imports
            fingerprint_str = f"{user_id}|{iso_date}|{str(row['description'])}|{amt}"
            fingerprint = hashlib.sha256(fingerprint_str.encode("utf-8")).hexdigest()

            record = {
                "user_id": user_id,
                "transaction_date": iso_date,
                "amount": amt,
                "currency": str(row.get('currency', 'INR') or 'INR'),
                "description": str(row['description']),
                "category": str(row.get('category', 'Uncategorized') or 'Uncategorized'),
                "merchant_name": str(row.get('merchant', row['description']) or row['description']),
                "payment_method": str(row.get('payment_method', 'unknown') or 'unknown'),
                "status": str(row.get('status', 'completed') or 'completed'),
                "fingerprint": fingerprint,
                "raw_data": {k: sanitize_value(v) for k, v in row.to_dict().items()},
            }
            records.append(record)
        except Exception as e:
            print(f"⚠️ Skipping row due to error: {e} | Row: {row.values}")

    if not records:
        print("⚠️ No valid records to insert.")
        return

    print(f"🚀 Inserting {len(records)} records for User {user_id}...")
    
    # Batch insert
    batch_size = 100
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        try:
            # Change to upsert to support idempotency based on fingerprint
            response = supabase.table("transactions").upsert(
                batch, on_conflict="fingerprint"
            ).execute()
            print(f"   Allowed batch {i}-{i+len(batch)}: Success") # .upsert returns data on success
        except Exception as e:
            print(f"❌ Batch insert failed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest transactions")
    parser.add_argument("file", help="Path to CSV/Excel file")
    parser.add_argument("--user_id", required=True, help="Target Supabase User ID (UUID)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.file):
        print(f"❌ File not found: {args.file}")
        sys.exit(1)
        
    ingest_file(args.file, args.user_id)
