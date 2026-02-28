import pytest
from packages.categorization.data_loader import BankStatementParser
from packages.categorization.cleaner import clean_description

# (Input, Expected Output)
# These are the "Golden" examples we want to protect against regression
TEST_CASES = [
    # Basic cleaning
    ("POS PURCHASE 12345678 STARBUCKS", "STARBUCKS"),
    ("ATM WDL 04-04-2024", ""),  # WDL removed, date removed
    ("UPI/12345/GOOGLEPAY", "GOOGLEPAY"),
    ("NEFT-SBIN0001234-RENT", "RENT"),
    # Real examples from audit
    # 1. FamPay with junk prefix
    (
        "POS ATM PURCH   OTHPG 3214073210 30RAZ*FamPay solutions puth Delhi",
        "FamPay solutions puth Delhi",
    ),
    # 2. UPI Transfer
    ("DEP TFR   UPI/CR/321428593292/SHAIK YA/SBIN/skya smeen1", "SHAIK YA skya smeen1"),
    # 3. Insufficient Balance (Location removal)
    (
        "WDL TFR   INSUFFICIENT BAL POS DECLINE CH ARGE   009993 AT 04413 PBB NELLORE",
        "INSUFFICIENT BAL DECLINE CH ARGE",
    ),
    # 4. Interest Credit
    ("INTERES T CREDIT", "INTERES T CREDIT"),  # Can we fix splitting? Maybe later.
    # 5. Swiggy
    ("POS ATM PURCH   OTHPG 3226109246 79SWIGGY", "SWIGGY"),
]


@pytest.mark.parametrize("raw, expected", TEST_CASES)
def test_cleaning_logic(raw, expected):
    # Initialize parser (file path doesn't matter for this static method test)
    parser = BankStatementParser("dummy.xlsx")
    cleaned = parser.clean_details(raw)

    # We might need to adjust expectations if current logic is different
    # This test acts as a "live documentation" of our cleaning rules
    assert cleaned == expected


def test_separator_standardization():
    """Separators like *, -, _ should be standardized to spaces."""
    # Various separators should become spaces
    assert "AMAZON" in clean_description("AMAZON*PAYMENTS")
    assert "SWIGGY" in clean_description("SWIGGY-FOOD")
    assert "ZOMATO" in clean_description("ZOMATO_FOOD")
