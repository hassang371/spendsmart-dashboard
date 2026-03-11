import sys

# Set up django/fastapi environment paths if needed
sys.path.append("/Users/hassangameryt/Documents/Antigravity/SCALE APP")
import asyncio

from apps.api.core.auth import get_service_client


async def test():
    client = get_service_client()
    try:
        data = [
            {
                "user_id": "90a4797f-3152-42d6-a773-12c183ce1deb",
                "transaction_date": "2024-01-01T00:00:00Z",
                "amount": 100,
                "currency": "INR",
                "description": "Test",
                "merchant_name": "Test",
                "category": "Test",
                "status": "completed",
                "type": "credit",
                "fingerprint": "test_fp_1234",
                "raw_data": {},
            }
        ]
        res = (
            client.table("transactions")
            .upsert(data, on_conflict="user_id, fingerprint", ignore_duplicates=True)
            .execute()
        )
        print("SUCCESS:", res)
    except Exception as e:
        print("ERROR:", str(e))
        import traceback

        traceback.print_exc()


asyncio.run(test())
