# packages/categorization/tests/test_rules.py
import pytest

from packages.categorization.rules import KeywordMatcher


@pytest.fixture
def matcher():
    return KeywordMatcher()


# Food — new additions
def test_dunzo_is_food(matcher):
    assert matcher.predict("Dunzo Quick Delivery") == "Food"


def test_bigbasket_is_food(matcher):
    assert matcher.predict("BigBasket grocery order") == "Food"


def test_eatfit_is_food(matcher):
    assert matcher.predict("EatFit meal plan") == "Food"


# Transport — new additions
def test_indrive_is_transport(matcher):
    assert matcher.predict("InDrive ride payment") == "Transport"


def test_indigo_is_transport(matcher):
    assert matcher.predict("IndiGo flight booking") == "Transport"


def test_makemytrip_is_transport(matcher):
    assert matcher.predict("MakeMyTrip hotel + flight") == "Transport"


# Entertainment — new additions
def test_jiocinema_is_entertainment(matcher):
    assert matcher.predict("JioCinema subscription") == "Entertainment"


def test_sonyliv_is_entertainment(matcher):
    assert matcher.predict("SonyLIV monthly plan") == "Entertainment"


def test_google_play_pass_is_entertainment(matcher):
    assert matcher.predict("Play Pass Monthly") == "Entertainment"


# Shopping — new additions
def test_nykaa_is_shopping(matcher):
    assert matcher.predict("Nykaa beauty order") == "Shopping"


def test_meesho_is_shopping(matcher):
    assert matcher.predict("Meesho fashion purchase") == "Shopping"


def test_croma_is_shopping(matcher):
    assert matcher.predict("Croma electronics") == "Shopping"


# Finance — new additions
def test_cred_is_finance(matcher):
    assert matcher.predict("CRED credit card payment") == "Finance"


def test_phonepay_is_finance(matcher):
    assert matcher.predict("PhonePe UPI transfer") == "Finance"


# Health — new additions
def test_onemg_is_health(matcher):
    assert matcher.predict("1mg medicine order") == "Health"


def test_cultfit_is_health(matcher):
    assert matcher.predict("Cult.fit gym membership") == "Health"


# Utilities — new additions
def test_tatapower_is_utilities(matcher):
    assert matcher.predict("Tata Power electricity bill") == "Utilities"


# Education — new additions
def test_byjus_is_education(matcher):
    assert matcher.predict("BYJU'S course subscription") == "Education"


def test_unacademy_is_education(matcher):
    assert matcher.predict("Unacademy Plus plan") == "Education"


from packages.categorization.constants import DEFAULT_CATEGORY_KEYWORDS


def test_each_category_has_at_least_8_seed_phrases():
    """Anchor seed phrases must be rich enough to position prototypes well."""
    for category, phrases in DEFAULT_CATEGORY_KEYWORDS.items():
        assert len(phrases) >= 8, f"{category} only has {len(phrases)} phrases — need >= 8"


def test_food_seeds_include_indian_apps():
    food = DEFAULT_CATEGORY_KEYWORDS.get("Food", [])
    assert any("swiggy" in p.lower() for p in food)
    assert any("blinkit" in p.lower() or "zepto" in p.lower() for p in food)


def test_entertainment_includes_subscriptions():
    ent = DEFAULT_CATEGORY_KEYWORDS.get("Entertainment", [])
    assert any("jiocinema" in p.lower() or "sonyliv" in p.lower() for p in ent)
