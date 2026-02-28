import pandas as pd
import msoffcrypto
import io
import os

file_path = "tests/fixtures/statement.xlsx"
password = os.getenv("STATEMENT_PASSWORD")

if not password:
    raise RuntimeError("Set STATEMENT_PASSWORD environment variable before running")

try:
    decrypted = io.BytesIO()
    with open(file_path, "rb") as f:
        file = msoffcrypto.OfficeFile(f)
        file.load_key(password=password)
        file.decrypt(decrypted)

    df = pd.read_excel(decrypted)

    print("--- SUCCESS ---")
    print(f"Rows: {len(df)}")
    print(f"Columns: {list(df.columns)}")
    print("--- ROWS 10-30 ---")
    print(df.iloc[10:30].to_string())

    # Check for likely description columns
    potential_cols = [
        c
        for c in df.columns
        if isinstance(c, str)
        and any(x in c.lower() for x in ["desc", "detail", "narration", "particular"])
    ]
    print(f"Potential Description Columns: {potential_cols}")

except Exception as e:
    print("--- ERROR ---")
    print(str(e))
