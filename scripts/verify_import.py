import sys
import os

# Add root to path so packages can be imported
sys.path.append(os.getcwd())

from packages.ingestion_engine.import_transactions import parse_file

file_path = "tests/fixtures/statement.xlsx"
password = os.getenv("STATEMENT_PASSWORD")

if not password:
    raise RuntimeError("Set STATEMENT_PASSWORD environment variable before running")

try:
    with open(file_path, "rb") as f:
        content = f.read()

    print(f"Parsing {file_path}...")
    df = parse_file(content, "statement.xlsx", password=password)

    print("\nColumns found:", df.columns.tolist())
    print("-" * 50)

    # Check if new columns exist
    expected = ["method", "entity", "ref", "location", "merchant"]
    for col in expected:
        if col not in df.columns:
            print(f"FAILED: Column {col} missing!")
        else:
            print(f"SUCCESS: Column {col} present.")

    print("-" * 50)
    print("Sample Data (First 5 rows):")
    cols_to_show = ["date", "merchant", "amount", "method", "entity", "ref", "location"]
    print(df[cols_to_show].head(10).to_string())

except Exception as e:
    print(f"ERROR: {e}")
    import traceback

    traceback.print_exc()
