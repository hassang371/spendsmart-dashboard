import re


class MerchantExtractor:
    def __init__(self):
        # Ordered list of known merchants (order matters for substring matching)
        self.known_merchants = [
            ("Swiggy Instamart", ["swiggy instamart", "instamart"]),
            ("Swiggy", ["swiggy"]),
            ("Zomato", ["zomato", "zomatofo"]),
            ("Uber", ["uber", "uber india"]),
            ("Ola", ["ola", "olacabs"]),
            ("Rapido", ["rapido"]),
            ("Blinkit", ["blinkit", "grofers"]),
            ("Zepto", ["zepto"]),
            ("BigBasket", ["bigbasket", "big basket"]),
            ("Amazon", ["amazon", "amzn"]),
            ("Flipkart", ["flipkart"]),
            ("Myntra", ["myntra"]),
            ("Ajio", ["ajio"]),
            ("Netflix", ["netflix"]),
            ("Spotify", ["spotify"]),
            ("Youtube", ["youtube", "google oct"]),
            ("Apple", ["apple.com", "itunes"]),
            ("Google", ["google"]),
            ("Jio", ["jio", "reliance jio"]),
            ("Airtel", ["airtel"]),
            ("Vodafone", ["vi", "vodafone"]),
            # Generic
            ("Mcdonalds", ["mcdonalds", "mcdonald"]),
            ("Starbucks", ["starbucks"]),
            ("KFC", ["kfc"]),
            ("Burger King", ["burger king"]),
            ("Domino's", ["dominos", "domino's"]),
            ("Pizza Hut", ["pizza hut"]),
            ("Subway", ["subway"]),
        ]

        self.noise_patterns = [
            r"UPI-[a-zA-Z0-9]+-",
            r"UPI/",
            r"NEFT-",
            r"IMPS-",
            r"Ach Debit",
            r"Pos",
            r"Wdl Tfr",
            r"Tfr",
            r"Dr",
            r"Cr",
            r"Mb",
            r"[0-9]+",  # Strip numbers
            r"\s+",  # Compress whitespace
        ]

    def extract(self, raw_description: str) -> str:
        if not raw_description:
            return ""

        # Normalize input
        cleaned = raw_description.lower()

        # Strategy 1: Known Merchant Matching
        # Check against known list first (highest confidence)
        for official_name, aliases in self.known_merchants:
            for alias in aliases:
                if alias in cleaned:
                    return official_name

        # Strategy 2: Specific UPI/P2P Patterns (High Precision)
        # Pattern: WDL TFR UPVDR/{digits}/{NAME}/{BANK}/...
        # Pattern: UPI/{digits}/{NAME}/{BANK}/...
        match = re.search(
            r"(?:UPI|UPVDR|UPS|IMPS|NEFT)(?:/|-)\d+(?:/|-)([^/]+)(?:/|-)",
            cleaned,
            re.IGNORECASE,
        )
        if match:
            potential_name = match.group(1).strip()
            # Clean up: remove trailing dots, dashes, digits
            potential_name = re.sub(r"[0-9._-]+$", "", potential_name).strip()

            # Filter out if potential name is just noise or empty
            if len(potential_name) > 2 and not re.match(r"^\d+$", potential_name):
                return potential_name.title()

        # Strategy 3: Heuristic Cleaning for Unknowns
        # Remove noise patterns
        for pattern in self.noise_patterns:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

        # Remove special chars and extra whitespace
        cleaned = re.sub(r"[^a-zA-Z\s]", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        # Strategy 3: Intelligent Truncation / Title Case
        return cleaned.title()
