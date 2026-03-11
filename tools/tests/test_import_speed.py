import time

import pandas as pd

print("Loading CSV...")
df = pd.read_csv("tools/upi_transactions_2024.csv")
print(f"Loaded {len(df)} rows.")

start = time.time()
print("Fingerprinting...")
fingerprints = []
import hashlib


def fp(d, a, m, s):
    return hashlib.sha256(f"{d}|{a}|{m}|{s}".encode()).hexdigest()


for idx, row in df.iterrows():
    tx = row.to_dict()
    fingerprints.append(
        fp(
            tx.get("timestamp", ""),
            tx.get("amount (inr)", 0),
            tx.get("merchant_category", ""),
            f"row_{idx}",
        )
    )
print(f"Fingerprinted in {time.time()-start:.2f}s")
