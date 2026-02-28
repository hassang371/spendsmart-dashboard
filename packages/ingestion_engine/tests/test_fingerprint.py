from packages.ingestion_engine.import_transactions import generate_fingerprint


def test_generate_fingerprint_consistency():
    """
    Test that the same transaction data always generates the same fingerprint.
    SHA256({ISO_Date_Sec}|{Amount_Float}|{Merchant_Normalized})
    """
    # Case 1: Standard transaction
    fp1 = generate_fingerprint("2026-02-12T10:00:00Z", 150.00, "Starbucks")
    fp2 = generate_fingerprint("2026-02-12T10:00:00Z", 150.00, "Starbucks")

    assert fp1 == fp2
    assert isinstance(fp1, str)
    assert len(fp1) == 64  # SHA256 hex digest length


def test_generate_fingerprint_normalization():
    """
    Test that minor variations in merchant name or whitespace don't affect the fingerprint.
    This effectively tests the normalization logic inside the fingerprint generation.
    """
    fp1 = generate_fingerprint("2026-02-12T10:00:00Z", 150.00, "Starbucks ")
    fp2 = generate_fingerprint("2026-02-12T10:00:00Z", 150.00, "STARBUCKS")

    assert fp1 == fp2


def test_generate_fingerprint_differentiation():
    """
    Test that different transactions have different fingerprints.
    """
    fp1 = generate_fingerprint("2026-02-12T10:00:00Z", 150.00, "Starbucks")
    fp2 = generate_fingerprint(
        "2026-02-12T10:00:01Z", 150.00, "Starbucks"
    )  # 1 second later
    fp3 = generate_fingerprint(
        "2026-02-12T10:00:00Z", 150.01, "Starbucks"
    )  # 1 cent different

    assert fp1 != fp2
    assert fp1 != fp3
