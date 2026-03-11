import re


class MerchantExtractor:
    def __init__(self):
        # Ordered by specificity — longer/more-specific names first
        self.known_merchants = [
            # Food
            ("Swiggy Instamart", ["swiggy instamart", "instamart"]),
            ("Swiggy", ["swiggy"]),
            ("Zomato", ["zomato"]),
            ("Blinkit", ["blinkit", "grofers"]),
            ("Zepto", ["zepto"]),
            ("BigBasket", ["bigbasket", "big basket"]),
            ("Dunzo", ["dunzo"]),
            ("EatFit", ["eatfit"]),
            ("Licious", ["licious"]),
            ("Box8", ["box8"]),
            ("JioMart", ["jiomart"]),
            ("Country Delight", ["country delight"]),
            ("Domino's", ["dominos", "domino's"]),
            ("McDonald's", ["mcdonalds", "mcdonald"]),
            ("KFC", ["kfc"]),
            ("Burger King", ["burger king"]),
            ("Pizza Hut", ["pizza hut"]),
            ("Starbucks", ["starbucks"]),
            ("Subway", ["subway"]),
            ("Haldiram's", ["haldiram"]),
            ("Barbeque Nation", ["barbeque nation"]),
            # Transport
            ("Uber", ["uber"]),
            ("Ola", ["olacabs", "ola cabs"]),
            ("Rapido", ["rapido"]),
            ("InDrive", ["indrive"]),
            ("BluSmart", ["blusmart"]),
            ("IRCTC", ["irctc"]),
            ("IndiGo", ["indigo", "6e"]),
            ("SpiceJet", ["spicejet"]),
            ("Air India", ["air india", "airindia"]),
            ("Vistara", ["vistara"]),
            ("MakeMyTrip", ["makemytrip"]),
            ("Ixigo", ["ixigo"]),
            ("redBus", ["redbus"]),
            ("Yatra", ["yatra"]),
            ("Goibibo", ["goibibo"]),
            ("HP Petrol", ["hpcl", "hp petrol", "hindustan petroleum"]),
            ("Indian Oil", ["iocl", "indianoil", "indian oil"]),
            ("Shell", ["shell petrol", "shell pump"]),
            # Shopping
            ("Amazon", ["amazon", "amzn"]),
            ("Flipkart", ["flipkart"]),
            ("Myntra", ["myntra"]),
            ("Ajio", ["ajio"]),
            ("Meesho", ["meesho"]),
            ("Nykaa", ["nykaa"]),
            ("Tata CLiQ", ["tata cliq", "tatacliq"]),
            ("Snapdeal", ["snapdeal"]),
            ("Decathlon", ["decathlon"]),
            ("Croma", ["croma"]),
            ("Reliance Digital", ["reliance digital"]),
            ("Vijay Sales", ["vijay sales"]),
            ("Zudio", ["zudio"]),
            ("Westside", ["westside"]),
            ("DMart", ["dmart", "d-mart"]),
            # Entertainment
            ("Netflix", ["netflix"]),
            ("Spotify", ["spotify"]),
            ("JioCinema", ["jiocinema"]),
            ("SonyLIV", ["sonyliv", "sony liv"]),
            ("ZEE5", ["zee5"]),
            ("Disney+ Hotstar", ["hotstar", "disney+"]),
            ("Amazon Prime", ["prime video", "amazon prime"]),
            ("Apple TV+", ["apple tv", "apple.com/bill"]),
            ("Mubi", ["mubi"]),
            ("Google Play", ["play pass", "google play"]),
            ("YouTube", ["youtube"]),
            ("Google One", ["google one", "cloud storage monthly", "google 200"]),
            ("JioSaavn", ["jiosaavn", "jio saavn"]),
            ("Gaana", ["gaana"]),
            ("BookMyShow", ["bookmyshow"]),
            ("PVR", ["pvr cinemas", "pvr cinema"]),
            ("INOX", ["inox"]),
            ("Steam", ["steam"]),
            # Utilities
            ("Airtel", ["airtel"]),
            ("Jio", ["reliance jio", "jio fiber", "jio prepaid"]),
            ("Vi (Vodafone)", ["vodafone", " vi ", "vi postpaid", "vi prepaid"]),
            ("BSNL", ["bsnl"]),
            ("ACT Fibernet", ["act fibernet", "act broadband"]),
            ("Hathway", ["hathway"]),
            ("Tata Power", ["tata power"]),
            ("BESCOM", ["bescom"]),
            ("BWSSB", ["bwssb"]),
            ("MSEDCL", ["msedcl"]),
            # Health
            ("Apollo Pharmacy", ["apollo pharmacy", "apollo247", "apollo 247"]),
            ("1mg", ["1mg", "tata 1mg"]),
            ("Netmeds", ["netmeds"]),
            ("Pharmeasy", ["pharmeasy"]),
            ("MedPlus", ["medplus"]),
            ("Cult.fit", ["cult.fit", "cultfit"]),
            ("Healthifyme", ["healthifyme"]),
            ("Practo", ["practo"]),
            # Finance
            ("Zerodha", ["zerodha"]),
            ("Groww", ["groww"]),
            ("Upstox", ["upstox"]),
            ("Angel One", ["angel one", "angelone"]),
            ("INDmoney", ["indmoney"]),
            ("CRED", ["cred "]),  # trailing space avoids matching "credit"
            ("PhonePe", ["phonepe", "phone pe"]),
            ("Paytm", ["paytm"]),
            ("Google Pay", ["gpay", "google pay", "tez"]),
            ("Bajaj Finance", ["bajaj finance", "bajaj finserv"]),
            # Education
            ("BYJU'S", ["byju", "byjus"]),
            ("Unacademy", ["unacademy"]),
            ("Vedantu", ["vedantu"]),
            ("upGrad", ["upgrad"]),
            ("Physics Wallah", ["physics wallah", "pw app"]),
            ("Udemy", ["udemy"]),
            ("Coursera", ["coursera"]),
            ("Simplilearn", ["simplilearn"]),
        ]

        self.noise_patterns = [
            r"UPI[-/][A-Z0-9]+[-/]",
            r"UPI[-/]",
            r"NEFT[-/]",
            r"RTGS[-/]",
            r"IMPS[-/]",
            r"ACH\s+D[-/]?",
            r"NACH\s+",
            r"ECS\s+",
            r"POS\s+",
            r"\b(DR|CR|MB|TFR|WDL|TFNR)\b",
        ]

    def extract(self, raw_description: str) -> str:
        """Extract a clean merchant name from a transaction description.

        Priority:
        1. Known merchant list (highest confidence, avoids false positives)
        2. UPI/NEFT structured format (parse payee segment)
        3. Clean description heuristic (strip noise, title-case)
        """
        if not raw_description:
            return ""

        cleaned_lower = raw_description.lower().strip()

        # Strategy 1: Known merchant matching (most precise)
        for official_name, aliases in self.known_merchants:
            for alias in aliases:
                if alias in cleaned_lower:
                    return official_name

        # Strategy 2: Structured UPI/NEFT format
        # e.g. "UPI/DR/123456/MERCHANT NAME/BANKCODE/vpa@bank"
        # e.g. "NEFT-HDFC0001234-MERCHANT NAME"
        match = re.search(
            r"(?:UPI|IMPS|NEFT|RTGS|UPVDR)(?:/|-)\d*(?:/|-)?([A-Za-z][^/\-@]{2,30})(?:[/\-@]|$)",
            raw_description,
            re.IGNORECASE,
        )
        if match:
            candidate = match.group(1).strip()
            candidate = re.sub(r"[0-9._]+$", "", candidate).strip()
            if len(candidate) > 2:
                return candidate.title()

        # Strategy 3: Clean description heuristic
        # Strip known noise tokens and return title-cased result
        cleaned = raw_description
        for pattern in self.noise_patterns:
            cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
        # Remove trailing digits/codes (e.g. "HD", "4K", reference numbers)
        cleaned = re.sub(r"\b[A-Z]{1,3}\d+\b", " ", cleaned)  # e.g. "6E1234"
        cleaned = re.sub(r"\b\d{4,}\b", " ", cleaned)  # long numbers
        cleaned = re.sub(r"[^a-zA-Z\s]", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        if not cleaned:
            return raw_description.title()

        # Take up to first 4 meaningful words
        words = [w for w in cleaned.split() if len(w) > 1]
        return " ".join(words[:4]).title()


def infer_payment_method(description: str) -> str:
    """Infer payment method from transaction description patterns.

    Returns one of: "UPI", "Bank Transfer", "IMPS", "Auto Debit",
                    "Cash", "Card", "Other"

    Note: subscription services (Netflix, YouTube, etc.) can be paid via
    any method — without a UPI/POS/NEFT marker in the description we
    cannot determine the method, so they fall through to "Other".
    """
    if not description:
        return "Other"

    d = description.upper()

    if d.startswith("UPI") or "UPI/" in d or "UPI-" in d:
        return "UPI"
    if "NEFT" in d or "RTGS" in d:
        return "Bank Transfer"
    if "IMPS" in d:
        return "IMPS"
    if "ACH" in d or "NACH" in d or "ECS" in d:
        return "Auto Debit"
    if "ATM" in d and ("WDL" in d or "CASH" in d or "WITHDRAW" in d):
        return "Cash"
    if "POS" in d or "SWIPE" in d or "CARD PURCHASE" in d:
        return "Card"

    return "Other"
