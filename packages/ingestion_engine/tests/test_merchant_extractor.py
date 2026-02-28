import pytest
from packages.ingestion_engine.merchant_extractor import MerchantExtractor


@pytest.fixture
def extractor():
    return MerchantExtractor()


def test_extract_known_merchants(extractor):
    # Case 1: UPI noise with clear merchant name
    assert (
        extractor.extract("WDL TFR UPI/DR/604239354584/Zomatofo/AIRP/zom") == "Zomato"
    )

    # Case 2: Swiggy in middle of string
    assert extractor.extract("UPI-55648-SWIGGY-FOOD-DELIVERY") == "Swiggy"

    # Case 3: Uber
    assert extractor.extract("UBER INDIA SYSTEMS PVT HEL") == "Uber"

    # Case 4: Amazon
    assert extractor.extract("AMAZON PAY INDIA PRIVATE LIMI") == "Amazon"


def test_clean_noise_generic(extractor):
    # Case 1: Simple POS transaction
    assert extractor.extract("POS 40593845 MCDONALDS") == "Mcdonalds"

    # Case 2: NEFT transfer (should return beneficiary if possible, or cleaned string)
    assert extractor.extract("NEFT-DR-HDFC-NETFLIX.COM") == "Netflix"


def test_fallback_logic(extractor):
    # Case 1: Unknown string, just clean special chars
    assert extractor.extract("Unknown   Store   123") == "Unknown Store"


def test_empty_input(extractor):
    assert extractor.extract("") == ""
    assert extractor.extract(None) == ""


def test_upi_p2p_extraction(extractor):
    # Case 1: Padma M
    raw_1 = "WDL TFR UPVDR/604194480414/Padma M/YESB/payt"
    assert extractor.extract(raw_1) == "Padma M"

    # Case 2: Faridha
    raw_2 = "WDL TFR UPVDR/604060117039/FARIDHA./FDRL/bha"
    assert extractor.extract(raw_2) == "Faridha"

    # Case 3: Transfer to Dad (generic P2P if not UPI pattern)
    # This might require broader logic, but let's test the UPI pattern first.
