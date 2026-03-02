import pytest
from packages.ingestion_engine.merchant_extractor import MerchantExtractor, infer_payment_method


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
    # Case 1: Simple POS transaction — returns official name from known_merchants
    assert extractor.extract("POS 40593845 MCDONALDS") == "McDonald's"

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


# Clean descriptions (current data style)
def test_youtube_premium_clean(extractor):
    assert extractor.extract("YouTube Premium Individual") == "YouTube"

def test_play_pass_clean(extractor):
    assert extractor.extract("Play Pass Monthly") == "Google Play"

def test_cloud_storage_clean(extractor):
    assert extractor.extract("Cloud Storage Monthly") == "Google One"

def test_music_premium_clean(extractor):
    result = extractor.extract("Music Premium")
    assert result == "Music Premium"

def test_movie_rental_clean(extractor):
    # Should NOT return "Vodafone" for "Movie Rental HD"
    result = extractor.extract("Movie Rental HD")
    assert result != "Vodafone"

def test_samay_raina_clean(extractor):
    result = extractor.extract("Samay Raina membership")
    assert "Samay Raina" in result

# UPI-style (future bank data)
def test_upi_swiggy(extractor):
    assert extractor.extract("UPI-SWIGGY INTERNET PVT LTD-swiggy@icici") == "Swiggy"

def test_upi_zomato(extractor):
    assert extractor.extract("UPI/DR/123456/ZOMATO/YESB/zomato@axl") == "Zomato"

# New brands
def test_nykaa(extractor):
    assert extractor.extract("Nykaa fashion order") == "Nykaa"

def test_meesho(extractor):
    assert extractor.extract("Meesho clothing purchase") == "Meesho"

def test_cred(extractor):
    assert extractor.extract("CRED credit card bill") == "CRED"

def test_phonepay(extractor):
    assert extractor.extract("PhonePe UPI payment") == "PhonePe"

def test_onemg(extractor):
    assert extractor.extract("1mg medicine order") == "1mg"

def test_cultfit(extractor):
    assert extractor.extract("Cult.fit gym plan") == "Cult.fit"

def test_jiocinema(extractor):
    assert extractor.extract("JioCinema subscription") == "JioCinema"

def test_indigo(extractor):
    assert extractor.extract("IndiGo flight PNR 6E1234") == "IndiGo"


# --- infer_payment_method tests ---

def test_upi_description():
    assert infer_payment_method("UPI-SWIGGY-pay@okaxis") == "UPI"

def test_neft_description():
    assert infer_payment_method("NEFT-HDFC0001234-SALARY") == "Bank Transfer"

def test_rtgs_description():
    assert infer_payment_method("RTGS/001/VENDOR PAYMENT") == "Bank Transfer"

def test_imps_description():
    assert infer_payment_method("IMPS/P2P/9876543210/Rahul") == "IMPS"

def test_ach_description():
    assert infer_payment_method("ACH D-BAJAJ FINANCE-123") == "Auto Debit"

def test_nach_description():
    assert infer_payment_method("NACH DEBIT HDFC BANK") == "Auto Debit"

def test_atm_description():
    assert infer_payment_method("ATM WDL 1234 KORAMANGALA") == "Cash"

def test_pos_description():
    assert infer_payment_method("POS PURCHASE ZARA STORE") == "Card"

def test_google_play_is_subscription():
    assert infer_payment_method("YouTube Premium Individual") == "Subscription"

def test_cloud_storage_is_subscription():
    assert infer_payment_method("Cloud Storage Monthly") == "Subscription"

def test_play_pass_is_subscription():
    assert infer_payment_method("Play Pass Monthly") == "Subscription"

def test_unknown_defaults_to_other():
    assert infer_payment_method("Random merchant description") == "Other"

def test_empty_defaults_to_other():
    assert infer_payment_method("") == "Other"
