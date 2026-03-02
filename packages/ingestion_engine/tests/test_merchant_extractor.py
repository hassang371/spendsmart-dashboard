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
