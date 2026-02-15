from typing import Dict, Optional
import re


class KeywordMatcher:
    def __init__(self):
        # Explicit rules: key -> category
        # Keys should be lowercase for case-insensitive matching
        self.rules: Dict[str, str] = {
            # Food & Dining
            "swiggy": "Food",
            "zomato": "Food",
            "blinkit": "Food",
            "zepto": "Food",
            "domin": "Food",  # Dominos
            "pizza": "Food",
            "burger": "Food",
            "kfc": "Food",
            "mcdonald": "Food",
            "starbuck": "Food",
            "cafe": "Food",
            "restaurant": "Food",
            # Transport
            "uber": "Transport",
            "ola": "Transport",
            "rapido": "Transport",
            "metro": "Transport",
            "irctc": "Transport",
            "fuel": "Transport",
            "petrol": "Transport",
            "shell": "Transport",
            # Shopping
            "amazon": "Shopping",
            "flipkart": "Shopping",
            "myntra": "Shopping",
            "ajio": "Shopping",
            "decathlon": "Shopping",
            "zudio": "Shopping",
            "retail": "Shopping",
            # Entertainment
            "netflix": "Entertainment",
            "spotify": "Entertainment",
            "prime": "Entertainment",
            "hotstar": "Entertainment",
            "youtube": "Entertainment",
            "steam": "Entertainment",
            "pvr": "Entertainment",
            "inox": "Entertainment",
            "bookmyshow": "Entertainment",
            # Utilities
            "bescom": "Utilities",
            "bwssb": "Utilities",
            "airtel": "Utilities",
            "jio": "Utilities",
            "vodafone": "Utilities",
            "vi": "Utilities",
            "act": "Utilities",  # ACT Fibernet
            "bill": "Utilities",
            # Health
            "pharmacy": "Health",
            "apollo": "Health",
            "medplus": "Health",
            "practo": "Health",
            "clinic": "Health",
            "hospital": "Health",
            "gym": "Health",
            "fitness": "Health",
            # Finance
            "zerodha": "Finance",
            "groww": "Finance",
            "angel": "Finance",  # Angel One
            "cred": "Finance",
            "loan": "Finance",
            "emi": "Finance",
            "insurance": "Finance",
            "tax": "Finance",
        }

    def predict(self, text: str) -> Optional[str]:
        """
        Check if text contains any known keywords.
        Returns Category if match found, else None.
        """
        if not text:
            return None

        text_lower = text.lower()

        # Exact match / Substring check
        # We iterate through rules. Order matters if keys overlap,
        # but dictionary iteration order is insertion-based in modern Python (3.7+).
        # To be safe, we could prioritize longer keys first if needed.

        for keyword, category in self.rules.items():
            # word boundary check for short keywords to avoid false positives (e.g. "act" inside "action")
            if len(keyword) <= 4:
                if re.search(r"\b" + re.escape(keyword) + r"\b", text_lower):
                    return category
            else:
                if keyword in text_lower:
                    return category

        return None
