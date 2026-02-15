import msoffcrypto
import pandas as pd
import io
import os

file_path = "tests/fixtures/statement.xlsx"
password = os.getenv("STATEMENT_PASSWORD")

if not password:
    raise RuntimeError("Set STATEMENT_PASSWORD environment variable before running")

try:
    decrypted_workbook = io.BytesIO()

    with open(file_path, "rb") as f:
        office_file = msoffcrypto.OfficeFile(f)
        office_file.load_key(password=password)
        office_file.decrypt(decrypted_workbook)

    df = pd.read_excel(decrypted_workbook)
    print("Columns:", df.columns.tolist())
    print("\nRow 16 (Headers):")
    print(df.iloc[16].tolist())
    print("\nRow 17 (First data):")
    print(df.iloc[17].tolist())

except Exception as e:
    print(f"Error: {e}")
