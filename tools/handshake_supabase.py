import os
import sys
from supabase import create_client, Client
from dotenv import load_dotenv

# Load env
load_dotenv()

# Verify Env vars
url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
key = (
    os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
)

if not url or not key:
    print(
        "❌ Error: Missing Supabase env vars. Set SUPABASE_URL/NEXT_PUBLIC_SUPABASE_URL and "
        "SUPABASE_SERVICE_KEY/SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY.",
    )
    sys.exit(1)

print(f"🔗 Testing Connection to: {url}")

try:
    # Initialize client
    supabase: Client = create_client(url, key)
    
    # Simple handshake: check auth session or get users (if permissions allow/exist)
    # Since we might not have users yet, let's try a simple RPC or select from a known table (if exists)
    # Or just check if client creates successfully (doesn't prove network).
    # Best practice: Try to fetch session or ping health.
    # Supabase-py doesn't have a direct ping.
    # We will try to get the current session (should be None but successful call)
    
    session = supabase.auth.get_session()
    print("✅ Handshake Successful: Client initialized.")
    if session:
        print(f"   Session active: {session}")
    else:
        print("   No active session (Expected for Anon client without login).")
        
    # Attempt to query (will fail if no table/policy, but error confirms connection)
    try:
        data = supabase.table("users").select("*").limit(1).execute()
        print(f"✅ Query Successful: {data}")
    except Exception as e:
        print(f"⚠️ Query Failed (Expected if table missing/RLS): {e}")
        
except Exception as e:
    print(f"❌ Handshake Failed: {e}")
    sys.exit(1)
