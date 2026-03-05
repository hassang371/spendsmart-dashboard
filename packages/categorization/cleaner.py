"""Transaction description preprocessing pipeline (v2.1).

Multi-stage text processing that produces three representations:
- raw:             Original bank string (stored for audit)
- informative:     Human-readable sentence (model input)
- merchant_name:   Clean display name (UI label)
- transaction_type: Structural tag for downstream logic

v2.1 improvements:
- IMPS: handle IBKL-xx154 patterns, standalone IMPS/REF/ACCOUNT, null fields
- POS: strip RetailCCA/RetailPOS terminal codes, leading digit-letter prefixes
- WDL TFR: detect declined/failed transactions
- DEP TFR: Gift / INB patterns with beneficiary extraction
- Fallback: better stripping of bare account numbers and noise tokens
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ProcessedText:
    """Multi-stage output from process_description()."""
    raw: str              # Original bank string
    informative: str      # "UPI Transfer to Allan G via YESB" (model input)
    merchant_name: str    # "Allan G" (UI display)
    transaction_type: str # "upi_transfer" | "pos_purchase" | "atm_withdrawal" | ...
    bank_name: Optional[str] = None # Optional extracted bank name (e.g. YESB)


# ── Bank Statement Lexicon ──────────────────────────────────────────────
# Maps banking abbreviations to human-readable English.

BANK_LEXICON = {
    "WDL TFR": "Withdrawal Transfer",
    "DEP TFR": "Deposit Transfer",
    "POS ATM PURCH": "Point of Sale Purchase",
    "ATM WDL": "ATM Withdrawal",
    "CEMTEX DEP": "Cash Deposit via Machine",
    "CASH DEPOSIT SELF": "Cash Deposit Self",
    "UPI/DR": "UPI Debit Transfer to",
    "UPI/CR": "UPI Credit Received from",
    "INB": "Internet Banking Transfer",
    "NEFT": "NEFT Transfer",
    "IMPS": "IMPS Transfer",
    "RTGS": "RTGS Transfer",
    "ACH": "Automated Clearing House",
}

# Known merchants for fuzzy matching
KNOWN_MERCHANTS: list[tuple[str, list[str]]] = [
    ("Swiggy Instamart", ["swiggy instamart", "instamart"]),
    ("Swiggy", ["swiggy"]),
    ("Zomato", ["zomato", "zomatofo", "payzomato", "zomatofood"]),
    ("Uber", ["uber"]),
    ("Ola", ["ola", "olacabs", "olamon"]),
    ("Rapido", ["rapido"]),
    ("Blinkit", ["blinkit"]),
    ("Zepto", ["zepto", "zeptonow"]),
    ("BigBasket", ["bigbasket"]),
    ("Amazon", ["amazon", "amzn", "amazonpay"]),
    ("Flipkart", ["flipkart"]),
    ("Myntra", ["myntra"]),
    ("Netflix", ["netflix"]),
    ("Spotify", ["spotify"]),
    ("YouTube", ["youtube", "google"]),
    ("Jio", ["jio", "reliance"]),
    ("Airtel", ["airtel"]),
    ("Vi (Vodafone Idea)", ["vodafone", "vi-", " vi "]),
    ("BSNL", ["bsnl"]),
    ("PhonePe", ["phonepe", "phonpe"]),
    ("Paytm", ["paytm", "one97communica", "one97"]),
    ("FamPay", ["fampay", "fampay solutions"]),
    ("Google Pay", ["googlepay", "gpay"]),
    ("CRED", ["cred"]),
    ("Dunzo", ["dunzo"]),
    ("Dream11", ["dream11"]),
    ("Groww", ["groww"]),
    ("Zerodha", ["zerodha"]),
    ("Meesho", ["meesho"]),
    ("Nykaa", ["nykaa"]),
    ("BookMyShow", ["bookmyshow"]),
    ("IRCTC", ["irctc"]),
    ("MakeMyTrip", ["makemytrip"]),
    ("Ixigo", ["ixigo"]),
    ("BESCOM", ["bescom"]),
    ("Domino's", ["dominos", "domino"]),
    ("McDonald's", ["mcdonalds", "mcdonald"]),
    ("KFC", ["kfc"]),
    ("Starbucks", ["starbucks"]),
    ("Burger King", ["burgerking", "burger king"]),
    ("Airbnb", ["airbnb"]),
    ("OYO", ["oyo", "oyorooms"]),
    ("Indian Oil", ["iocl", "indian oil", "indianoil"]),
    ("HP Petrol", ["hpcl", "hindustan petroleum"]),
    ("BPCL", ["bpcl", "bharat petroleum"]),
    ("LIC", ["lic", "life insurance"]),
    ("SBI", ["sbi", "state bank"]),
    ("HDFC", ["hdfc"]),
    ("ICICI", ["icici"]),
    ("Axis Bank", ["axis bank", "axisbank"]),
    ("Kotak", ["kotak"]),
]

# Noise tokens commonly found in bank strings that carry no useful meaning
_NOISE_TOKENS = re.compile(
    r"\b(AT|OF|FROM|TO|VIA|REF|UTR|NEFT|RTGS|IMPS|UPI|INB|TFR|CR|DR|"
    r"null|NULL|IBKL|xx154|XX154|AIRP|UPII|SP|GY|RE1)\b",
    re.IGNORECASE,
)

# Retail terminal codes: 223RetailCCA, 711RetailPOS, etc.
_RETAIL_TERMINAL_RE = re.compile(r"\b\d{1,4}(RetailCCA|RetailPOS|Retail)\b", re.IGNORECASE)

# Pure account/reference numbers (8+ digits)
_ACCOUNT_NUM_RE = re.compile(r"\b\d{8,}\b")

# IMPS reference pattern: IMPS/NNN/IBKL-xx154 -null/... (standalone)
_IMPS_STANDALONE_RE = re.compile(
    r"IMPS/(\d+)/([^/\s]+)\s*[-]?\s*(null|NULL)?\s*/?(.*)", re.IGNORECASE
)


def _match_known_merchant(*fields: str) -> Optional[str]:
    """Match text fields against known merchants. Returns official name or None."""
    # Space-removed combined check (catches e.g. "olacabs" vs "ola cabs")
    # Skip aliases that are too short after space removal — they risk false-positives
    # (e.g. "vi" matching "via", or "to" matching everywhere).
    combined = " ".join(fields).replace(" ", "").lower()
    for official, aliases in KNOWN_MERCHANTS:
        for alias in aliases:
            alias_stripped = alias.replace(" ", "")
            if len(alias_stripped) >= 3 and alias_stripped in combined:
                return official
    # Full-text check with spaces preserved (supports " vi " word boundary trick)
    text = " ".join(fields).lower()
    for official, aliases in KNOWN_MERCHANTS:
        for alias in aliases:
            if alias in text:
                return official
    return None


def _clean_name(raw: str) -> str:
    """Clean up a raw name: collapse spaces, strip trailing punctuation, title case."""
    name = re.sub(r"\s{2,}", " ", raw).strip()
    name = re.sub(r"[._\-/]+$", "", name).strip()
    if name and name == name.upper():
        name = name.title()
    return name


def _strip_noise(text: str) -> str:
    """Strip pure noise tokens and account numbers from a string."""
    text = _NOISE_TOKENS.sub(" ", text)
    text = _ACCOUNT_NUM_RE.sub(" ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


def _normalize_raw(text: str) -> str:
    """Normalize newlines and excessive whitespace in raw bank text."""
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


def _extract_imps_name(part2: str, part3: str) -> str:
    """Extract a beneficiary name from IMPS parts, stripping reference noise."""
    combined = f"{part2} {part3}"
    # Strip IBKL-xx154 style codes
    combined = re.sub(r"\b[A-Z]{4}\d*-?[Xx]+\d*\b", "", combined, flags=re.IGNORECASE)
    # Strip ref prefixes like RE1-XX218-
    combined = re.sub(r"\b[A-Z0-9]{2,}-[A-Z0-9]{2,}-\b", "", combined, flags=re.IGNORECASE)
    # Strip null/NULL
    combined = re.sub(r"\bnull\b", "", combined, flags=re.IGNORECASE)
    # Strip trailing account numbers
    combined = re.sub(r"\d{8,}", "", combined)
    # Strip slashes
    combined = combined.replace("/", " ").replace("*", " ")
    combined = _strip_noise(combined)
    name = _clean_name(combined)
    return name if len(name) > 1 else ""


def process_description(text: str) -> ProcessedText:
    """Process a raw bank transaction description into multi-stage output.

    Args:
        text: Raw transaction description from bank statement.

    Returns:
        ProcessedText with raw, informative, merchant_name, and transaction_type.
    """
    if not text or not text.strip():
        return ProcessedText(
            raw=text or "",
            informative="",
            merchant_name="",
            transaction_type="unknown",
        )

    raw_original = text
    text = _normalize_raw(text)

    # ── 1. UPI Transactions ──────────────────────────────────────────────
    # Format: (WDL|DEP) TFR UPI/(DR|CR)/<UTR>/<NAME>/<BANK>/<UPI_ID>/<APP>...
    upi_regex = (
        r"(?:WDL|DEP) TFR\s+UPI/(DR|CR)/([^/]+)/([^/]+)/([^/]+)/([^/]+)/(\S+)"
    )
    upi_match = re.search(upi_regex, text)
    if upi_match:
        mode, utr, raw_name, bank, raw_upi_id, raw_app = upi_match.groups()
        name = _clean_name(raw_name)
        upi_id = _clean_name(raw_upi_id)
        app = _clean_name(raw_app)
        is_credit = mode == "CR"

        # Only match known merchants against the name field.
        known = _match_known_merchant(name)
        merchant = known or name

        if is_credit:
            informative = f"UPI Received from {merchant} via {bank}"
        else:
            informative = f"UPI Transfer to {merchant} via {bank}"

        return ProcessedText(
            raw=raw_original,
            informative=informative,
            merchant_name=merchant,
            transaction_type="upi_transfer",
            bank_name=bank,
        )

    # ── 1.b UPI Ref Transactions (No Name) ────────────────────────────────
    # Format: Dep Tfr Upi/Ref/120485013116/Cr...
    upi_ref_regex = r"(WDL|DEP) TFR UPI/REV?/([^/]+)/(.*)"
    upi_ref_match = re.search(upi_ref_regex, text, re.IGNORECASE)
    if upi_ref_match:
        mode, ref, rest = upi_ref_match.groups()
        is_credit = mode.upper() == "DEP"
        # Try to extract location/merchant from rest
        loc_clean = _strip_noise(rest)
        loc_name = _clean_name(loc_clean)
        if loc_name and len(loc_name) > 2:
            informative = f"UPI {'Received' if is_credit else 'Payment'} at {loc_name}"
            merchant = loc_name
        else:
            informative = f"UPI {'Received (Ref: ' + ref + ')' if is_credit else 'Payment (Ref: ' + ref + ')'}"
            merchant = "UPI Transfer"

        return ProcessedText(
            raw=raw_original,
            informative=informative,
            merchant_name=merchant,
            transaction_type="upi_transfer",
            bank_name=None,
        )

    # ── 2. POS Transactions ──────────────────────────────────────────────
    pos_regex = r"POS ATM PURCH\s+(\S+)\s+(\S+)\s+(.*)$"
    pos_match = re.search(pos_regex, text)
    if pos_match:
        gateway, ref, remaining = pos_match.groups()
        parts = remaining.split()
        location = parts[-1] if len(parts) > 1 else ""
        merchant_raw = " ".join(parts[:-1]) if len(parts) > 1 else remaining

        # Strip RetailCCA/RetailPOS terminal codes (e.g. "36Paytm_ONE97")
        merchant_raw = _RETAIL_TERMINAL_RE.sub("", merchant_raw).strip()
        # Clean up: "17Pho*PHONEPE RECHARGE" → "PHONEPE RECHARGE"
        merchant = re.sub(r"^\d+[a-zA-Z0-9]*\*", "", merchant_raw).strip()
        # Strip leading digits+letter prefix like "36Swiggy" → "Swiggy"
        merchant = re.sub(r"^\d{1,3}([A-Za-z])", r"\1", merchant).strip()
        # Strip underscore-encoded names like "Paytm_ONE97COMMUNICA"
        merchant = merchant.replace("_", " ")

        known = _match_known_merchant(merchant, merchant_raw)
        if known:
            merchant = known
        else:
            merchant = _clean_name(merchant)

        loc_str = f" in {_clean_name(location)}" if location else ""
        informative = f"POS Purchase at {merchant}{loc_str}"

        return ProcessedText(
            raw=raw_original,
            informative=informative,
            merchant_name=merchant,
            transaction_type="pos_purchase",
            bank_name=None,
        )

    # ── 2.b RetailCCA / RetailPOS standalone (no POS ATM PURCH prefix) ──
    # e.g. "223RetailCCA", "711RetailPOS"
    retail_match = _RETAIL_TERMINAL_RE.search(text)
    if retail_match:
        # Strip the terminal code and see what remains
        cleaned = _RETAIL_TERMINAL_RE.sub("", text)
        cleaned = _strip_noise(cleaned)
        name = _clean_name(cleaned)
        known = _match_known_merchant(text, name)
        merchant = known or (name if len(name) > 1 else "Retail Store")
        return ProcessedText(
            raw=raw_original,
            informative=f"POS Purchase at {merchant}",
            merchant_name=merchant,
            transaction_type="pos_purchase",
            bank_name=None,
        )

    # ── 3. ATM Withdrawals ───────────────────────────────────────────────
    atm_regex = r"ATM WDL\s+ATM CASH\s+(.*)"
    atm_match = re.search(atm_regex, text)
    if atm_match:
        rest = atm_match.group(1).strip()
        parts = rest.split()
        atm_id = parts[0] if parts else ""
        location_start = 1
        if len(parts) > 1 and len(parts[1]) <= 3:
            atm_id = f"{parts[0]} {parts[1]}"
            location_start = 2
        location = " ".join(parts[location_start:])
        loc_str = f" at {_clean_name(location)}" if location else ""
        informative = f"ATM Cash Withdrawal{loc_str}"

        return ProcessedText(
            raw=raw_original,
            informative=informative,
            merchant_name="ATM Withdrawal",
            transaction_type="atm_withdrawal",
            bank_name=None,
        )

    # ── 4. Internet Banking ──────────────────────────────────────────────
    inb_regex = r"WDL TFR\s+INB\s+(.*?)(?:\.\.\.|$)"
    inb_match = re.search(inb_regex, text)
    if inb_match:
        merchant_part = inb_match.group(1).strip()
        # Remove trailing "AT <digits>" patterns
        merchant_part = re.sub(r"\s+AT\s+\d+.*$", "", merchant_part)
        merchant = _clean_name(merchant_part)
        known = _match_known_merchant(merchant)
        if known:
            merchant = known
        informative = f"Internet Banking Transfer: {merchant}"

        return ProcessedText(
            raw=raw_original,
            informative=informative,
            merchant_name=merchant,
            transaction_type="internet_banking",
            bank_name=None,
        )

    # ── 4.a IMPS Transactions ──────────────────────────────────────────────
    # Full: (WDL|DEP) TFR IMPS/<ref>/<part2>/<part3>
    imps_regex = r"(WDL|DEP) TFR IMPS/([^/\s]+)/([^/]*)/?(.*)"
    imps_match = re.search(imps_regex, text, re.IGNORECASE)
    if imps_match:
        mode, ref, part2, part3 = imps_match.groups()
        name = _extract_imps_name(part2, part3)

        # Try known merchant match on the full remaining text
        known = _match_known_merchant(part2, part3, text)
        if known:
            name = known

        is_credit = mode.upper() == "DEP"
        display = name or "IMPS Transfer"
        informative = f"IMPS {'Received from' if is_credit else 'Transfer to'} {display}"

        return ProcessedText(
            raw=raw_original,
            informative=informative,
            merchant_name=display,
            transaction_type="imps_transfer",
            bank_name=None,
        )

    # ── 4.b Standalone IMPS reference (no WDL/DEP prefix) ────────────────
    # e.g. "IMPS/500616690029/IBKL-xx154 -null/ 0097867162094"
    standalone_imps = _IMPS_STANDALONE_RE.search(text)
    if standalone_imps:
        ref, ibkl_code, null_part, rest = standalone_imps.groups()
        name = _extract_imps_name(ibkl_code or "", rest or "")
        known = _match_known_merchant(rest or "")
        display = known or (name if name else "IMPS Transfer")
        return ProcessedText(
            raw=raw_original,
            informative=f"IMPS Transfer (Ref: {ref})",
            merchant_name=display,
            transaction_type="imps_transfer",
            bank_name=None,
        )

    # ── 4.c NEFT Transactions ──────────────────────────────────────────────
    neft_regex = r"(WDL|DEP) TFR NEFT\*([^\*]+)\*([^\*]+)\*(.*)"
    neft_match = re.search(neft_regex, text, re.IGNORECASE)
    if neft_match:
        mode, bank_ifsc, ref, rest = neft_match.groups()
        # Extract letters as name:
        name_match = re.search(r"^[A-Za-z\s]+", rest)
        name = _clean_name(name_match.group(0)) if name_match else "Unknown"
        is_credit = mode.upper() == "DEP"
        informative = f"NEFT {'Received from' if is_credit else 'Transfer to'} {name}"

        return ProcessedText(
            raw=raw_original,
            informative=informative,
            merchant_name=name if name != "Unknown" else "NEFT Transfer",
            transaction_type="neft_transfer",
            bank_name=bank_ifsc[:4].upper() if len(bank_ifsc) >= 4 else None,
        )

    # ── 5. Cash Deposits ─────────────────────────────────────────────────
    if "CASH DEPOSIT SELF" in text:
        branch = re.sub(r"^.*CASH DEPOSIT SELF\s*(?:AT\s*)?", "", text).strip()
        loc_str = f" at {_clean_name(branch)}" if branch else ""
        informative = f"Cash Deposit{loc_str}"

        return ProcessedText(
            raw=raw_original,
            informative=informative,
            merchant_name="Self Deposit",
            transaction_type="cash_deposit",
            bank_name=None,
        )

    # CDM
    cdm_regex = r"CEMTEX DEP\s+(\S+)"
    cdm_match = re.search(cdm_regex, text)
    if cdm_match:
        ref = cdm_match.group(1)
        known = _match_known_merchant(text)
        if known:
            informative = f"CDM Deposit via {known} (Ref: {ref})"
            merchant = known
        else:
            informative = f"CDM Deposit (Ref: {ref})"
            merchant = "Cash Deposit Machine"

        return ProcessedText(
            raw=raw_original,
            informative=informative,
            merchant_name=merchant,
            transaction_type="cash_deposit",
            bank_name=None,
        )

    # ── 6. Interest / Bank Credits ───────────────────────────────────────
    interest_patterns = [
        (r"INTERES\w*\s*T?\s*CREDIT", "Interest Credit"),
        (r"INT\.\s*ON\s", "Interest Credit"),
    ]
    for pattern, label in interest_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return ProcessedText(
                raw=raw_original,
                informative=label,
                merchant_name=label,
                transaction_type="bank_credit",
                bank_name=None,
            )

    # ── 6.b Declined / Failed / Insufficient balance transactions ─────────
    declined_keywords = [
        "INSUFFICIENT BAL", "INSUFF", "DECLINED", "DECLINE",
        "POS DECLINE", "FAILED",
    ]
    is_declined = any(kw in text.upper() for kw in declined_keywords)
    if is_declined:
        # Try to extract merchant from what remains
        cleaned = text
        for kw in declined_keywords:
            cleaned = re.sub(kw, "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"WDL TFR|POS ATM PURCH|OTHPG", "", cleaned, flags=re.IGNORECASE)
        cleaned = _strip_noise(cleaned)
        name = _clean_name(cleaned)
        known = _match_known_merchant(text)
        merchant = known or (name if len(name) > 2 else "Failed Transaction")
        return ProcessedText(
            raw=raw_original,
            informative=f"Declined/Failed: {merchant}",
            merchant_name=merchant,
            transaction_type="declined",
            bank_name=None,
        )

    # ── 7. DEP TFR patterns (refunds, VISA-IN-RMT, Gift, INB) ────────────
    dep_match = re.search(r"DEP TFR\s+(.*)", text)
    if dep_match:
        rest = dep_match.group(1)
        known = _match_known_merchant(rest)
        if known:
            return ProcessedText(
                raw=raw_original,
                informative=f"Refund from {known}",
                merchant_name=known,
                transaction_type="refund",
                bank_name=None,
            )

        # Gift / transfer with beneficiary name
        gift_match = re.search(
            r"(?:Gift to relatives\s*/\s*Friends|INB|Transfer to Family.*?(?:\bOF\b))\s+(.*?)(?:\d{9,}|$)",
            rest, re.IGNORECASE
        )
        if gift_match:
            name = _clean_name(gift_match.group(1))
            if name and len(name) > 2:
                return ProcessedText(
                    raw=raw_original,
                    informative=f"Transfer to {name}",
                    merchant_name=name,
                    transaction_type="bank_transfer",
                    bank_name=None,
                )

        # VISA-IN-RMT refund
        visa_match = re.search(r"VISA-IN-RMT:(\w+)(\w{4})", rest)
        if visa_match:
            known = _match_known_merchant(rest)
            merchant = known or "Refund"
            return ProcessedText(
                raw=raw_original,
                informative=f"Refund from {merchant}",
                merchant_name=merchant,
                transaction_type="refund",
                bank_name=None,
            )

    # ── 8. WDL TFR patterns not caught above ─────────────────────────────
    wdl_match = re.search(r"WDL TFR\s+(.*)", text)
    if wdl_match:
        rest = wdl_match.group(1)
        known = _match_known_merchant(rest)
        if known:
            return ProcessedText(
                raw=raw_original,
                informative=f"Payment to {known}",
                merchant_name=known,
                transaction_type="upi_transfer",
                bank_name=None,
            )

    # ── Fallback: strip noise and display what remains ────────────────────
    # Remove known structural prefixes
    cleaned_fb = re.sub(
        r"^(WDL TFR|DEP TFR|POS ATM PURCH|OTHPG\s*\S+|UPI|IMPS|NEFT|RTGS)\s*",
        "", text, flags=re.IGNORECASE
    ).strip()
    cleaned_fb = _strip_noise(cleaned_fb)
    known_fb = _match_known_merchant(text, cleaned_fb)
    if known_fb:
        return ProcessedText(
            raw=raw_original,
            informative=f"Payment to {known_fb}",
            merchant_name=known_fb,
            transaction_type="unknown",
            bank_name=None,
        )

    display_fb = _clean_name(cleaned_fb) if cleaned_fb else _clean_name(text)
    return ProcessedText(
        raw=raw_original,
        informative=display_fb or _clean_name(text),
        merchant_name=display_fb or _clean_name(text),
        transaction_type="unknown",
        bank_name=None,
    )


def clean_description(text: str) -> str:
    """Backward-compatible wrapper. Returns the informative text.

    This function is kept so existing code that imports clean_description()
    continues to work without modification.
    """
    if not text:
        return ""
    result = process_description(text)
    return result.informative
