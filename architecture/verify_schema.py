import os
import sys
from supabase import create_client, Client
from dotenv import load_dotenv

# Try loading from multiple locations to be safe
load_dotenv()
load_dotenv("apps/web/.env.local")

url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")

if not url or not key:
    print("❌ Missing Supabase env vars")
    sys.exit(1)

try:
    supabase: Client = create_client(url, key)
except Exception as e:
    print(f"❌ Failed to initialize Supabase client: {e}")
    sys.exit(1)

def verify():
    print("Verifying schema...")
    failures = []

    # 1. Check transactions table for is_manual
    try:
        # Try to select is_manual from a single row. 
        res = supabase.table("transactions").select("is_manual").limit(1).execute()
        # If successfully selected, check if it's in the data (even if data is empty, keys might be present? No, data is list of dicts)
        # But if the column didn't exist, the API usually throws an error 
        # (PostgREST error: Could not find the field is_manual in the schema or View)
        print("✅ Column 'is_manual' exists in 'transactions'")
    except Exception as e:
        # We expect this to fail initially
        failures.append(f"Column 'is_manual' missing in 'transactions' (or error accessing it): {e}")

    # 2. Check classification_jobs table
    try:
        res = supabase.table("classification_jobs").select("id").limit(1).execute()
        print("✅ Table 'classification_jobs' exists")
    except Exception as e:
        failures.append(f"Table 'classification_jobs' missing: {e}")

    if failures:
        print("\n❌ Verification FAILED:")
        for f in failures:
            print(f"- {f}")
        sys.exit(1)
    else:
        print("\n✅ Verification PASSED")
        sys.exit(0)

if __name__ == "__main__":
    verify()
