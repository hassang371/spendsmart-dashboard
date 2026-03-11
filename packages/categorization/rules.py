"""Keyword-based transaction categorization rules (v2).

Fast O(1) deterministic matching layer. Runs BEFORE the neural network
classifier to instantly resolve known merchants/patterns.
"""

import re

from packages.categorization.constants import Category


class KeywordMatcher:
    """Deterministic keyword matcher for transaction descriptions.

    Matches cleaned transaction text against known vendors and patterns.
    Returns category with confidence 1.0 for exact matches.
    """

    def __init__(self) -> None:
        self._rules = self._build_rules()
        self._p2p_debit_pattern = re.compile(
            r"(?:transfer\s+to|sent\s+to|paid\s+to|payment\s+to|upi\s+(?:debit\s+)?transfer\s+to"
            r"|neft\s+(?:dr|debit)\b|imps\s+(?:dr|debit)\b|rtgs\s+(?:dr|debit)\b)",
            re.IGNORECASE,
        )
        self._p2p_credit_pattern = re.compile(
            r"(?:received\s+from|credit\s+from|upi\s+received\s+from|upi\s+credit\s+from"
            r"|neft\s+(?:cr|credit)\b|imps\s+(?:cr|credit)\b|rtgs\s+(?:cr|credit)\b"
            r"|(?:neft|imps|rtgs)[/-][A-Z][A-Za-z\s]{2,}-[A-Z]{2,})",
            re.IGNORECASE,
        )

    def _build_rules(self) -> list[tuple[str, list[str]]]:
        """Build keyword rules mapping vendors to categories.

        Rules are ordered from most specific to least. Each rule is a
        (category, [keywords]) tuple. Matching is case-insensitive substring.
        """
        return [
            # ── Food & Dining ────────────────────────────────────────────
            (
                Category.GROCERIES.value,
                [
                    "blinkit",
                    "zepto",
                    "bigbasket",
                    "jiomart",
                    "instamart",
                    "grocery",
                    "swiggy instamart",
                    "dunzo grocery",
                    "dmart",
                    "reliance fresh",
                    "more supermarket",
                    "nature basket",
                ],
            ),
            (
                Category.COFFEE_SNACKS.value,
                [
                    "starbucks",
                    "cafe coffee",
                    "third wave",
                    "chaayos",
                    "blue tokai",
                    "barista",
                    "bakery",
                    "pastry",
                    "chai point",
                ],
            ),
            (
                Category.FOOD.value,
                [
                    "swiggy",
                    "zomato",
                    "food",
                    "restaurant",
                    "dining",
                    "dunzo food",
                    "eatfit",
                    "dominos",
                    "domino",
                    "kfc",
                    "burger king",
                    "mcdonalds",
                    "mcdonald",
                    "pizza hut",
                    "subway",
                    "haldiram",
                    "barbeque nation",
                    "box8",
                    "faasos",
                    "behrouz",
                ],
            ),
            # ── Transport ────────────────────────────────────────────────
            (
                Category.TAXI_RIDESHARE.value,
                [
                    "uber",
                    "ola",
                    "rapido",
                    "bluesmart",
                ],
            ),
            (
                Category.PUBLIC_TRANSIT.value,
                [
                    "metro",
                    "irctc",
                    "redbus",
                    "train ticket",
                    "bus ticket",
                    "railway",
                    "smartcard",
                ],
            ),
            (
                Category.FLIGHTS.value,
                [
                    "indigo",
                    "spicejet",
                    "air india",
                    "vistara",
                    "goair",
                    "akasa",
                    "airline",
                    "flight",
                ],
            ),
            (
                Category.FUEL.value,
                [
                    "petrol",
                    "diesel",
                    "hpcl",
                    "iocl",
                    "bpcl",
                    "fuel",
                    "fastag",
                    "toll",
                    "indian oil",
                    "bharat petroleum",
                ],
            ),
            # ── Housing & Utilities ──────────────────────────────────────
            (
                Category.RENT_MORTGAGE.value,
                [
                    "rent",
                    "mortgage",
                    "landlord",
                    "housing society",
                    "nobroker",
                    "nestaway",
                ],
            ),
            (
                Category.ELECTRICITY_WATER.value,
                [
                    "electric",
                    "bescom",
                    "tata power",
                    "bwssb",
                    "water bill",
                    "gas cylinder",
                    "lpg",
                ],
            ),
            (
                Category.INTERNET_PHONE.value,
                [
                    "airtel",
                    "jio",
                    "vodafone",
                    "vi recharge",
                    "vi prepaid",
                    "vi postpaid",
                    "bsnl",
                    "act fibernet",
                    "broadband",
                    "recharge",
                ],
            ),
            (
                Category.HOME_MAINTENANCE.value,
                [
                    "plumber",
                    "electrician",
                    "carpenter",
                    "home repair",
                    "pest control",
                    "urban company",
                    "urbanclap",
                ],
            ),
            # ── Shopping ─────────────────────────────────────────────────
            (
                Category.CLOTHING_FASHION.value,
                [
                    "myntra",
                    "ajio",
                    "meesho fashion",
                    "nykaa",
                    "h&m",
                    "zara",
                    "westside",
                    "pantaloons",
                    "shoppers stop",
                    "lifestyle",
                    "max fashion",
                ],
            ),
            (
                Category.ELECTRONICS.value,
                [
                    "croma",
                    "reliance digital",
                    "laptop",
                    "computer",
                    "electronic",
                    "gadget",
                    "smartwatch",
                ],
            ),
            (
                Category.GENERAL_RETAIL.value,
                [
                    "amazon",
                    "flipkart",
                    "meesho",
                    "decathlon",
                    "online shopping",
                ],
            ),
            # ── Entertainment ────────────────────────────────────────────
            (
                Category.SUBSCRIPTIONS.value,
                [
                    "netflix",
                    "spotify",
                    "jiocinema",
                    "sonyliv",
                    "hotstar",
                    "youtube",
                    "play pass",
                    "apple music",
                    "subscription",
                    "prime video",
                ],
            ),
            (
                Category.MOVIES_EVENTS.value,
                [
                    "bookmyshow",
                    "pvr",
                    "inox",
                    "cinema",
                    "concert",
                    "event",
                    "theater",
                ],
            ),
            (
                Category.GAMING.value,
                [
                    "dream11",
                    "steam",
                    "playstation",
                    "xbox",
                    "game pass",
                    "in-app purchase",
                    "mpl",
                ],
            ),
            # ── Health ───────────────────────────────────────────────────
            (
                Category.MEDICAL.value,
                [
                    "hospital",
                    "doctor",
                    "clinic",
                    "diagnostic",
                    "health checkup",
                    "apollo clinic",
                    "fortis",
                    "max healthcare",
                    "practo",
                ],
            ),
            (
                Category.PHARMACY.value,
                [
                    "pharmacy",
                    "1mg",
                    "netmeds",
                    "pharmeasy",
                    "apollo pharmacy",
                    "medicine",
                ],
            ),
            (
                Category.FITNESS.value,
                [
                    "cultfit",
                    "cult.fit",
                    "gym",
                    "yoga",
                    "fitness",
                    "healthifyme",
                    "gold gym",
                ],
            ),
            # ── Finance ──────────────────────────────────────────────────
            (
                Category.INVESTMENTS.value,
                [
                    "zerodha",
                    "groww",
                    "upstox",
                    "mutual fund",
                    "sip",
                    "investment",
                ],
            ),
            (
                Category.INSURANCE.value,
                [
                    "insurance",
                    "policy premium",
                    "bajaj allianz",
                    "lic premium",
                    "hdfc life",
                ],
            ),
            (
                Category.LOAN_EMI.value,
                [
                    "loan",
                    "emi",
                    "bajaj finance",
                    "installment",
                ],
            ),
            (
                Category.TAXES.value,
                [
                    "income tax",
                    "gst payment",
                    "property tax",
                    "tax challan",
                    "tds",
                ],
            ),
            (
                Category.BANK_FEES.value,
                [
                    "bank charge",
                    "processing fee",
                    "convenience fee",
                    "maintenance charge",
                    "sms alert charge",
                    "atm surcharge",
                    "penalty fee",
                ],
            ),
            # ── Travel & Lodging ─────────────────────────────────────────
            (
                Category.HOTELS_STAYS.value,
                [
                    "airbnb",
                    "oyo",
                    "treebo",
                    "fabhotel",
                    "hotel",
                    "resort",
                    "homestay",
                    "booking.com",
                    "goibibo hotel",
                    "trivago",
                ],
            ),
            (
                Category.TRAVEL_BOOKING.value,
                [
                    "makemytrip",
                    "ixigo",
                    "cleartrip",
                    "yatra",
                    "goibibo",
                    "travel",
                    "trip",
                ],
            ),
            # ── Income ───────────────────────────────────────────────────
            (
                Category.SALARY.value,
                [
                    "salary",
                    "payroll",
                    "stipend",
                    "wages",
                ],
            ),
            (
                Category.REFUNDS.value,
                [
                    "refund",
                    "cashback",
                    "reversal",
                    "return order",
                ],
            ),
            (
                Category.INTEREST.value,
                [
                    "interest credit",
                    "fd maturity",
                    "interest earned",
                ],
            ),
            # ── Finance (CRED) ───────────────────────────────────────────
            (
                Category.BANK_FEES.value,
                [
                    "cred",
                ],
            ),
        ]

    def predict(self, text: str) -> dict | None:
        """Match text against keyword rules.

        Args:
            text: Cleaned or informative transaction description.

        Returns:
            {"category": str, "confidence": 1.0} if matched, None otherwise.
        """
        if not text:
            return None

        lower = text.lower()

        # ── P2P Transfer Detection ───────────────────────────────────────
        # Must run before keyword rules so "UPI Transfer to Allan" doesn't
        # match "transfer" as a generic keyword.
        # Use original text for patterns that match uppercase names (e.g. SBI NEFT-NAME-BANK)
        if self._p2p_debit_pattern.search(text):
            # Check it's not a known merchant being paid via UPI
            for _, keywords in self._rules:
                for kw in keywords:
                    if kw in lower:
                        return {"category": _, "confidence": 1.0}
            return {
                "category": Category.TRANSFERS_TO_PEOPLE.value,
                "confidence": 1.0,
            }

        if self._p2p_credit_pattern.search(text):
            for _, keywords in self._rules:
                for kw in keywords:
                    if kw in lower:
                        return {"category": _, "confidence": 1.0}
            return {
                "category": Category.RECEIVED_FROM_PEOPLE.value,
                "confidence": 1.0,
            }

        # ── Standard Keyword Matching ────────────────────────────────────
        for category, keywords in self._rules:
            for kw in keywords:
                if kw in lower:
                    return {"category": category, "confidence": 1.0}

        return None
