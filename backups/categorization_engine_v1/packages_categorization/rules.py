from typing import Dict, Optional
import re


class KeywordMatcher:
    def __init__(self):
        # Explicit rules: key -> category
        # Keys should be lowercase for case-insensitive matching.
        # predict() sorts by key length (longest first) so multi-word keys
        # like "tata power" match before shorter overlapping keys like "tata".
        self.rules: Dict[str, str] = {
            # ── Food & Dining ──────────────────────────────────────────────────
            "swiggy":          "Food",
            "zomato":          "Food",
            "blinkit":         "Food",
            "zepto":           "Food",
            "bigbasket":       "Food",
            "dunzo":           "Food",
            "eatfit":          "Food",
            "licious":         "Food",
            "box8":            "Food",
            "freshmenu":       "Food",
            "milkbasket":      "Food",
            "jiomart":         "Food",
            "domin":           "Food",   # Dominos
            "pizza":           "Food",
            "burger":          "Food",
            "kfc":             "Food",
            "mcdonald":        "Food",
            "starbuck":        "Food",
            "cafe":            "Food",
            "restaurant":      "Food",
            "barbeque":        "Food",
            "haldiram":        "Food",
            "amul":            "Food",
            "country delight": "Food",
            "faasos":          "Food",
            "behrouz":         "Food",
            "biryani":         "Food",
            "ola foods":       "Food",

            # ── Transport ──────────────────────────────────────────────────────
            "bharat petroleum": "Transport",
            "air india":       "Transport",
            "makemytrip":      "Transport",
            "uber":            "Transport",
            "rapido":          "Transport",
            "indrive":         "Transport",
            "blusmart":        "Transport",
            "metro":           "Transport",
            "irctc":           "Transport",
            "indigo":          "Transport",
            "spicejet":        "Transport",
            "airindia":        "Transport",
            "vistara":         "Transport",
            "goair":           "Transport",
            "akasa":           "Transport",
            "ixigo":           "Transport",
            "redbus":          "Transport",
            "yatra":           "Transport",
            "goibibo":         "Transport",
            "cleartrip":       "Transport",
            "fuel":            "Transport",
            "petrol":          "Transport",
            "diesel":          "Transport",
            "shell":           "Transport",
            "hpcl":            "Transport",
            "iocl":            "Transport",
            "indianoil":       "Transport",
            "parking":         "Transport",
            "fastag":          "Transport",
            "ksrtc":           "Transport",
            "bmtc":            "Transport",
            "ola":             "Transport",

            # ── Shopping ───────────────────────────────────────────────────────
            "reliance digital": "Shopping",
            "tata cliq":       "Shopping",
            "max fashion":     "Shopping",
            "big bazaar":      "Shopping",
            "vijay sales":     "Shopping",
            "amazon":          "Shopping",
            "flipkart":        "Shopping",
            "myntra":          "Shopping",
            "ajio":            "Shopping",
            "meesho":          "Shopping",
            "nykaa":           "Shopping",
            "snapdeal":        "Shopping",
            "decathlon":       "Shopping",
            "croma":           "Shopping",
            "zudio":           "Shopping",
            "westside":        "Shopping",
            "lifestyle":       "Shopping",
            "pantaloons":      "Shopping",
            "dmart":           "Shopping",
            "retail":          "Shopping",

            # ── Entertainment ──────────────────────────────────────────────────
            "apple tv":        "Entertainment",
            "music premium":   "Entertainment",
            "movie rental":    "Entertainment",
            "cloud storage":   "Entertainment",
            "play pass":       "Entertainment",
            "google play":     "Entertainment",
            "samay raina":     "Entertainment",
            "netflix":         "Entertainment",
            "spotify":         "Entertainment",
            "prime":           "Entertainment",
            "hotstar":         "Entertainment",
            "jiocinema":       "Entertainment",
            "sonyliv":         "Entertainment",
            "zee5":            "Entertainment",
            "mubi":            "Entertainment",
            "lionsgate":       "Entertainment",
            "gaana":           "Entertainment",
            "jiosaavn":        "Entertainment",
            "wynk":            "Entertainment",
            "youtube":         "Entertainment",
            "steam":           "Entertainment",
            "pvr":             "Entertainment",
            "inox":            "Entertainment",
            "bookmyshow":      "Entertainment",

            # ── Utilities ──────────────────────────────────────────────────────
            "act fibernet":    "Utilities",
            "you broadband":   "Utilities",
            "tata power":      "Utilities",
            "bescom":          "Utilities",
            "bwssb":           "Utilities",
            "msedcl":          "Utilities",
            "tneb":            "Utilities",
            "bses":            "Utilities",
            "airtel":          "Utilities",
            "vodafone":        "Utilities",
            "hathway":         "Utilities",
            "bsnl":            "Utilities",
            "tikona":          "Utilities",
            "bill":            "Utilities",
            "recharge":        "Utilities",
            "jio":             "Utilities",

            # ── Health ─────────────────────────────────────────────────────────
            "pharmacy":        "Health",
            "apollo":          "Health",
            "medplus":         "Health",
            "practo":          "Health",
            "1mg":             "Health",
            "netmeds":         "Health",
            "pharmeasy":       "Health",
            "healthifyme":     "Health",
            "cult.fit":        "Health",
            "cultfit":         "Health",
            "lybrate":         "Health",
            "portea":          "Health",
            "clinic":          "Health",
            "hospital":        "Health",
            "gym":             "Health",
            "fitness":         "Health",

            # ── Finance ────────────────────────────────────────────────────────
            "bajaj finance":   "Finance",
            "axis bank":       "Finance",
            "mutual fund":     "Finance",
            "zerodha":         "Finance",
            "groww":           "Finance",
            "angel":           "Finance",  # Angel One
            "upstox":          "Finance",
            "indmoney":        "Finance",
            "phonepe":         "Finance",
            "phonepay":        "Finance",
            "paytm":           "Finance",
            "cred":            "Finance",
            "loan":            "Finance",
            "insurance":       "Finance",
            "hdfc":            "Finance",
            "icici":           "Finance",
            "kotak":           "Finance",
            "tax":             "Finance",
            "sip":             "Finance",
            "gpay":            "Finance",
            "sbi":             "Finance",
            "emi":             "Finance",

            # ── Education ──────────────────────────────────────────────────────
            "physics wallah":  "Education",
            "byju":            "Education",
            "unacademy":       "Education",
            "vedantu":         "Education",
            "upgrad":          "Education",
            "simplilearn":     "Education",
            "udemy":           "Education",
            "coursera":        "Education",
            "course":          "Education",
            "tuition":         "Education",

            # ── Salary / Income ────────────────────────────────────────────────
            "salary":          "Salary",
            "payroll":         "Salary",
            "stipend":         "Salary",
        }

    def predict(self, text: str) -> Optional[str]:
        """
        Check if text contains any known keywords.
        Returns Category if match found, else None.

        Longer keywords are tested first so that multi-word keys like
        "tata power" match before shorter overlapping keys like "tata".
        Short keywords (<=4 chars) use word-boundary matching to avoid
        false positives (e.g. "emi" inside "premium", "jio" inside "jiocinema").
        """
        if not text:
            return None

        text_lower = text.lower()

        for keyword in sorted(self.rules.keys(), key=len, reverse=True):
            category = self.rules[keyword]
            if len(keyword) <= 4:
                if re.search(r"\b" + re.escape(keyword) + r"\b", text_lower):
                    return category
            else:
                if keyword in text_lower:
                    return category

        return None
