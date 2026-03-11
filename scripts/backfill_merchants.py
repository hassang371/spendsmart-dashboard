#!/usr/bin/env python3
"""One-time backfill: apply MerchantExtractor + infer_payment_method to all transactions.

Usage:
    .venv/bin/python scripts/backfill_merchants.py

Reads SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY from .env (or environment).
"""

import os
import sys

# Allow importing project packages
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from packages.ingestion_engine.merchant_extractor import (
    MerchantExtractor,
    infer_payment_method,
)
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]


def main():
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    extractor = MerchantExtractor()

    # Fetch all transactions (paginate in batches of 1000)
    offset = 0
    batch_size = 1000
    total_updated = 0

    while True:
        res = (
            client.table("transactions")
            .select("id, description, merchant_name, payment_method")
            .range(offset, offset + batch_size - 1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            break

        for row in rows:
            desc = row.get("description") or ""
            old_merchant = row.get("merchant_name") or ""
            old_method = row.get("payment_method") or ""

            new_merchant = extractor.extract(desc) if desc else old_merchant
            new_method = infer_payment_method(desc) if not old_method else old_method

            updates = {}
            if new_merchant and new_merchant != old_merchant:
                updates["merchant_name"] = new_merchant
            if new_method and new_method != old_method:
                updates["payment_method"] = new_method

            if updates:
                client.table("transactions").update(updates).eq("id", row["id"]).execute()
                total_updated += 1
                print(
                    f"  Updated {row['id'][:8]}... merchant={updates.get('merchant_name', '-')}, method={updates.get('payment_method', '-')}"
                )

        print(f"Processed {offset + len(rows)} rows so far ({total_updated} updated)")
        if len(rows) < batch_size:
            break
        offset += batch_size

    print(f"\nDone. {total_updated} transactions updated.")


if __name__ == "__main__":
    main()
