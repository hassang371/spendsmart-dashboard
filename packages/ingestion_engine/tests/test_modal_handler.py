from unittest.mock import patch
import pandas as pd

# We'll import the handler function we are about to create
# from packages.ingestion_engine.modal_app import process_upload


def test_process_upload_logic():
    """
    Test the Modal function logic:
    1. Receives file bytes.
    2. Parses CSV.
    3. Adds fingerprints.
    4. Returns JSON-serializable list of transactions.
    """
    # Create a dummy CSV
    csv_content = b"Date,Description,Amount\n2026-02-12,Test Transaction,100.00"

    # Mock the database insertion or just return the data for now as per beta plan
    # The Beta plan says "pushes the clean data to Supabase".
    # For this unit test, we'll verify it calls the logic and returns structured data.

    with patch(
        "packages.ingestion_engine.import_transactions.parse_csv_content"
    ) as mock_parse:
        # Mock what the parse function returns (we proved it works in other tests)
        mock_df = pd.DataFrame(
            [
                {
                    "date": "2026-02-12",
                    "description": "Test Transaction",
                    "amount": 100.00,
                    "merchant": "Test Transaction",
                }
            ]
        )
        mock_parse.return_value = mock_df

        # We need to import the function inside the test if the file doesn't exist yet,
        # but standard TDD requires the file to exist but function maybe absent or empty.
        from packages.ingestion_engine.modal_app import process_file_logic

        result = process_file_logic(csv_content)

        assert len(result) == 1
        assert result[0]["amount"] == 100.00
        assert "fingerprint" in result[0]
        assert len(result[0]["fingerprint"]) == 64
