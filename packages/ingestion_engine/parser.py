"""
Bank Statement Parser - Enhanced ingestion engine for multiple bank formats.

Supports: HDFC, ICICI, SBI, Axis, and generic formats.
Features: Auto-detection, date normalization, amount normalization,
          structured transaction extraction (UPI/POS/ATM/INB).
"""

import re
import io
import logging
from typing import Optional, Dict, List, Any, Callable
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from .merchant_extractor import MerchantExtractor

logger = logging.getLogger(__name__)


@dataclass
class ParsedTransaction:
    """Standardized transaction structure."""

    date: datetime
    amount: float
    description: str
    transaction_type: str
    category: str
    merchant: str
    method: str = ""  # UPI, POS, ATM, INB, CASH, etc.
    entity: str = ""  # Extracted merchant/entity name
    reference: str = ""  # Transaction reference number
    location: str = ""  # Location if available
    raw_data: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for DataFrame creation."""
        return {
            "date": self.date,
            "amount": self.amount,
            "description": self.description,
            "type": self.transaction_type,
            "category": self.category,
            "merchant": self.merchant,
            "method": self.method,
            "entity": self.entity,
            "reference": self.reference,
            "location": self.location,
            "raw_data": self.raw_data or {},
        }


class BankFormatDetector:
    """Detects bank format from file headers and content."""

    # Bank-specific header patterns
    BANK_PATTERNS = {
        "hdfc": {
            "headers": ["date", "description", "debit", "credit", "balance"],
            "keywords": ["hdfc", "bank", "statement"],
            "description_patterns": [
                r"UPI/[A-Z]+/\d+/[^/]+/",  # UPI pattern
                r"POS\s+",  # POS pattern
                r"ATM\s+WDL",  # ATM pattern
            ],
        },
        "icici": {
            "headers": ["date", "particulars", "debit", "credit", "balance"],
            "keywords": ["icici", "bank", "statement"],
            "description_patterns": [
                r"UPI-[A-Z]+-\d+-",
                r"POS\s+",
                r"ATM\s+",
            ],
        },
        "sbi": {
            "headers": ["date", "description", "debit", "credit", "balance"],
            "keywords": ["sbi", "state bank", "statement"],
            "description_patterns": [
                r"UPI/[A-Z]+/\d+/[^/]+/",
                r"POS\s+",
                r"ATM\s+WDL",
            ],
        },
        "axis": {
            "headers": ["date", "particulars", "debit", "credit", "balance"],
            "keywords": ["axis", "bank", "statement"],
            "description_patterns": [
                r"UPI/[A-Z]+/\d+/[^/]+/",
                r"POS\s+",
                r"ATM\s+",
            ],
        },
        "generic": {
            "headers": ["date", "description", "amount"],
            "keywords": [],
            "description_patterns": [],
        },
    }

    @classmethod
    def detect_from_headers(cls, columns: List[str]) -> str:
        """Detect bank type from column headers."""
        columns_lower = [str(c).lower().strip() for c in columns]

        scores = {}
        for bank, patterns in cls.BANK_PATTERNS.items():
            score = 0
            expected_headers = patterns["headers"]

            for header in expected_headers:
                if any(header in col for col in columns_lower):
                    score += 1

            scores[bank] = score / len(expected_headers) if expected_headers else 0

        # Return bank with highest score, minimum 0.5 threshold
        if scores:
            best_match = max(scores, key=scores.get)
            if scores[best_match] >= 0.5:
                return best_match

        return "generic"

    @classmethod
    def detect_from_content(cls, df: pd.DataFrame) -> str:
        """Detect bank type from content patterns."""
        if df.empty or "description" not in df.columns:
            return "generic"

        # Sample first 100 descriptions
        descriptions = df["description"].dropna().astype(str).head(100).str.lower()

        scores = {}
        for bank, patterns in cls.BANK_PATTERNS.items():
            if bank == "generic":
                continue

            score = 0
            for pattern in patterns["description_patterns"]:
                matches = descriptions.str.contains(pattern, regex=True, na=False).sum()
                score += matches

            scores[bank] = score / len(descriptions) if len(descriptions) > 0 else 0

        if scores:
            best_match = max(scores, key=scores.get)
            if scores[best_match] >= 0.1:  # At least 10% match
                return best_match

        return "generic"


class TransactionExtractor:
    """Extracts structured information from transaction descriptions."""

    # Transaction type patterns
    PATTERNS = {
        "UPI": {
            "regex": [
                r"UPI/([A-Z]+)/(\d+)/([^/]+)/([^/]+)/?([^/\s]*)",  # HDFC/SBI style
                r"UPI-([A-Z]+)-(\d+)-([^/]+)-",  # ICICI style
            ],
            "extractor": "extract_upi",
        },
        "POS": {
            "regex": [
                r"POS\s+(?:PURCH|DEBIT|CREDIT)?\s*(\d*)\s*([^\d].*?)(?:\s+\d{2}[/-]\d{2})?$",
                r"POS\s+(.*?)(?:\s+\d{4})?$",
            ],
            "extractor": "extract_pos",
        },
        "ATM": {
            "regex": [
                r"ATM\s+(?:WDL|DEP|WITHDRAWAL|DEPOSIT)\s*(\d*)\s*(.*)",
                r"ATM\s+(.*)",
            ],
            "extractor": "extract_atm",
        },
        "INB": {
            "regex": [
                r"INB\s+(.*?)(?:\s+\d{4})?$",
                r"IB\s+(.*?)(?:\s+\d{4})?$",
            ],
            "extractor": "extract_inb",
        },
        "NEFT": {
            "regex": [
                r"NEFT-[A-Z]*-?(\d+)-([^-]+)",
                r"NEFT/[^/]+/(\d+)/([^/]+)",
            ],
            "extractor": "extract_neft",
        },
        "IMPS": {
            "regex": [
                r"IMPS-[A-Z]*-?(\d+)-([^-]+)",
                r"IMPS/[^/]+/(\d+)/([^/]+)",
            ],
            "extractor": "extract_imps",
        },
        "CASH": {
            "regex": [
                r"CASH\s+(?:DEPOSIT|WITHDRAWAL|DEP|WDL)\s+(.*)",
                r"CASH\s+(.*)",
            ],
            "extractor": "extract_cash",
        },
    }

    def __init__(self):
        self.merchant_extractor = MerchantExtractor()

    def extract(self, description: str) -> Dict[str, str]:
        """Extract structured info from description."""
        if not description:
            return {"method": "", "entity": "", "reference": "", "location": ""}

        description = str(description).strip()

        # Try each pattern type
        for method, config in self.PATTERNS.items():
            for regex in config["regex"]:
                match = re.search(regex, description, re.IGNORECASE)
                if match:
                    extractor_func = getattr(self, config["extractor"])
                    result = extractor_func(description, match)
                    result["method"] = method
                    return result

        # Default: use merchant extractor
        entity = self.merchant_extractor.extract(description)
        return {"method": "", "entity": entity, "reference": "", "location": ""}

    def extract_upi(self, description: str, match: re.Match) -> Dict[str, str]:
        """Extract UPI transaction details."""
        groups = match.groups()
        mode = groups[0] if len(groups) > 0 else ""
        ref = groups[1] if len(groups) > 1 else ""
        name = groups[2] if len(groups) > 2 else ""

        # Clean up name
        name = re.sub(r"[0-9._-]+$", "", name).strip()

        # Try merchant extraction on name
        entity = self.merchant_extractor.extract(name) or name.title()

        return {
            "entity": entity,
            "reference": ref,
            "location": "",
            "meta": {"mode": mode},
        }

    def extract_pos(self, description: str, match: re.Match) -> Dict[str, str]:
        """Extract POS transaction details."""
        groups = match.groups()
        ref = groups[0] if len(groups) > 0 and groups[0] else ""
        merchant = groups[1] if len(groups) > 1 else description

        # Clean and extract merchant
        merchant = merchant.strip()
        entity = self.merchant_extractor.extract(merchant) or merchant.title()

        # Try to extract location (usually last word if uppercase)
        location = ""
        words = merchant.split()
        if words and words[-1].isupper() and len(words[-1]) > 2:
            location = words[-1]

        return {"entity": entity, "reference": ref, "location": location}

    def extract_atm(self, description: str, match: re.Match) -> Dict[str, str]:
        """Extract ATM transaction details."""
        groups = match.groups()
        ref = groups[0] if len(groups) > 0 and groups[0] else ""
        location = groups[1] if len(groups) > 1 else ""

        return {
            "entity": "ATM Withdrawal",
            "reference": ref,
            "location": location.strip(),
        }

    def extract_inb(self, description: str, match: re.Match) -> Dict[str, str]:
        """Extract INB (Internet Banking) transaction details."""
        groups = match.groups()
        details = groups[0] if len(groups) > 0 else description

        entity = self.merchant_extractor.extract(details) or details.title()

        return {"entity": entity, "reference": "", "location": ""}

    def extract_neft(self, description: str, match: re.Match) -> Dict[str, str]:
        """Extract NEFT transaction details."""
        groups = match.groups()
        ref = groups[0] if len(groups) > 0 else ""
        entity = groups[1] if len(groups) > 1 else ""

        return {"entity": entity.strip().title(), "reference": ref, "location": ""}

    def extract_imps(self, description: str, match: re.Match) -> Dict[str, str]:
        """Extract IMPS transaction details."""
        return self.extract_neft(description, match)  # Same pattern

    def extract_cash(self, description: str, match: re.Match) -> Dict[str, str]:
        """Extract Cash transaction details."""
        groups = match.groups()
        location = groups[0] if len(groups) > 0 else ""

        return {
            "entity": "Cash Transaction",
            "reference": "",
            "location": location.strip(),
        }


class ProgressTracker:
    """Tracks progress for large file processing."""

    def __init__(self, total: int, callback: Optional[Callable] = None):
        self.total = total
        self.current = 0
        self.callback = callback
        self.last_percent = 0

    def update(self, increment: int = 1):
        """Update progress."""
        self.current += increment
        percent = int((self.current / self.total) * 100)

        if percent != self.last_percent and percent % 10 == 0:
            self.last_percent = percent
            if self.callback:
                self.callback(percent)
            else:
                logger.info(f"Processing: {percent}%")

    def finish(self):
        """Mark as complete."""
        if self.callback:
            self.callback(100)


class BankStatementParser:
    """
    Main parser class for bank statements.

    Supports multiple bank formats with automatic detection and
    structured transaction extraction.
    """

    # Date format patterns to try
    DATE_FORMATS = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%y",
        "%d-%m-%y",
        "%m/%d/%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
    ]

    def __init__(
        self,
        file_path: Optional[str] = None,
        file_content: Optional[bytes] = None,
        bank_type: Optional[str] = None,
        password: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
    ):
        """
        Initialize parser.

        Args:
            file_path: Path to the file (optional if file_content provided)
            file_content: File content as bytes (optional if file_path provided)
            bank_type: Bank type override (hdfc, icici, sbi, axis, generic)
            password: Password for encrypted files
            progress_callback: Callback function(percent) for progress updates
        """
        self.file_path = file_path
        self.file_content = file_content
        self.bank_type = bank_type
        self.password = password
        self.progress_callback = progress_callback
        self.detector = BankFormatDetector()
        self.extractor = TransactionExtractor()
        self.merchant_extractor = MerchantExtractor()

        if not file_path and not file_content:
            raise ValueError("Either file_path or file_content must be provided")

    def detect_bank_type(self, df: pd.DataFrame, columns: List[str]) -> str:
        """Detect bank type from headers and content."""
        if self.bank_type:
            return self.bank_type.lower()

        # Try header-based detection first
        header_based = self.detector.detect_from_headers(columns)

        # Try content-based detection
        content_based = self.detector.detect_from_content(df)

        # Prefer content-based if it's specific
        if content_based != "generic":
            return content_based

        return header_based

    def _read_file(self) -> pd.DataFrame:
        """Read file into DataFrame."""
        # Get file content
        if self.file_content:
            content = self.file_content
        elif self.file_path:
            with open(self.file_path, "rb") as f:
                content = f.read()
        else:
            raise ValueError("No file content available")

        # Determine file type from path or content
        if self.file_path:
            file_ext = Path(self.file_path).suffix.lower()
        else:
            # Detect from content when no file path provided
            file_ext = self._detect_file_type(content)

        if file_ext in [".xlsx", ".xls"]:
            return self._read_excel(content)
        elif file_ext == ".csv":
            return self._read_csv(content)
        else:
            # Try CSV first, then Excel
            try:
                return self._read_csv(content)
            except Exception:
                return self._read_excel(content)

    def _detect_file_type(self, content: bytes) -> str:
        """Detect file type from content magic numbers."""
        if content.startswith(b"PK\x03\x04"):
            # ZIP format = modern Excel (.xlsx)
            return ".xlsx"
        elif content.startswith(b"\xd0\xcf\x11\xe0"):
            # OLE2 format = old Excel (.xls)
            return ".xls"
        else:
            # Default to CSV for text-based formats
            return ".csv"

    def _read_csv(self, content: bytes) -> pd.DataFrame:
        """Read CSV content."""
        # Try different encodings
        encodings = ["utf-8", "latin-1", "iso-8859-1", "cp1252"]

        for encoding in encodings:
            try:
                df = pd.read_csv(io.BytesIO(content), encoding=encoding)
                return df
            except UnicodeDecodeError:
                continue

        raise ValueError("Could not decode CSV file with any known encoding")

    def _read_excel(self, content: bytes) -> pd.DataFrame:
        """Read Excel content, handling encrypted files."""
        try:
            # Try to read without password first
            return pd.read_excel(io.BytesIO(content))
        except Exception as e:
            if self.password:
                # Try to decrypt
                try:
                    import msoffcrypto

                    decrypted = io.BytesIO()
                    with io.BytesIO(content) as f:
                        office_file = msoffcrypto.OfficeFile(f)
                        office_file.load_key(password=self.password)
                        office_file.decrypt(decrypted)
                    decrypted.seek(0)
                    return pd.read_excel(decrypted)
                except ImportError:
                    raise ValueError(
                        "Encrypted Excel file requires 'msoffcrypto-tool' package. "
                        "Install with: pip install msoffcrypto-tool"
                    )
                except Exception as decrypt_error:
                    raise ValueError(f"Failed to decrypt file: {decrypt_error}")
            else:
                raise ValueError(
                    f"Could not read Excel file. If encrypted, provide password. Error: {e}"
                )

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names to standard format."""
        column_mappings = {
            # Date columns
            "date": [
                "date",
                "transaction date",
                "txn date",
                "value date",
                "posting date",
                "time",
                "timestamp",
            ],
            # Description columns
            "description": [
                "description",
                "particulars",
                "details",
                "narration",
                "transaction details",
                "remarks",
                "notes",
                "merchant_category",
                "product",
            ],
            # Amount columns
            "debit": [
                "debit",
                "debit amount",
                "withdrawal",
                "dr",
                "dr amount",
                "outflow",
            ],
            "credit": [
                "credit",
                "credit amount",
                "deposit",
                "cr",
                "cr amount",
                "inflow",
            ],
            "amount": [
                "amount",
                "transaction amount",
                "txn amount",
                "amount (inr)",
                "amount (usd)",
                "amount (eur)",
            ],
            # Balance columns
            "balance": ["balance", "closing balance", "running balance"],
            # Type columns
            "type": ["type", "transaction type", "txn type", "dr/cr"],
        }

        # Create reverse mapping
        reverse_map = {}
        for standard, variants in column_mappings.items():
            for variant in variants:
                reverse_map[variant] = standard

        # Normalize column names
        new_columns = {}
        for col in df.columns:
            col_lower = str(col).lower().strip()
            if col_lower in reverse_map:
                new_columns[col] = reverse_map[col_lower]
            else:
                new_columns[col] = col_lower

        df = df.rename(columns=new_columns)

        return df

    def _find_header_row(self, df: pd.DataFrame) -> int:
        """Find the header row in the DataFrame."""
        # Check if first row looks like headers
        for i in range(min(20, len(df))):
            row_values = [str(v).lower() for v in df.iloc[i].values]

            # Look for date + description + amount patterns
            has_date = any("date" in v for v in row_values)
            has_desc = any(
                any(x in v for x in ["desc", "particular", "detail", "narration"])
                for v in row_values
            )
            has_amount = any(
                any(x in v for x in ["amount", "debit", "credit", "dr", "cr"])
                for v in row_values
            )

            if has_date and has_desc and has_amount:
                return i

        return 0  # Assume first row is header

    def _parse_date(self, date_value) -> Optional[datetime]:
        """Parse date with multiple format support."""
        if pd.isna(date_value):
            return None

        # If already datetime
        if isinstance(date_value, datetime):
            return date_value

        date_str = str(date_value).strip()

        # Try pandas to_datetime first
        try:
            parsed = pd.to_datetime(date_str, dayfirst=True)
            if pd.notna(parsed):
                return parsed.to_pydatetime()
        except Exception:
            pass

        # Try specific formats
        for fmt in self.DATE_FORMATS:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return None

    def _parse_amount(self, amount_value) -> float:
        """Parse amount, handling currency symbols and commas."""
        if pd.isna(amount_value):
            return 0.0

        if isinstance(amount_value, (int, float)):
            return float(amount_value)

        # Clean amount string
        amount_str = str(amount_value)

        # Remove currency symbols and whitespace
        amount_str = re.sub(r"[₹$€£¥\s]", "", amount_str)

        # Handle parentheses for negative numbers
        if "(" in amount_str and ")" in amount_str:
            amount_str = "-" + amount_str.replace("(", "").replace(")", "")

        # Remove commas
        amount_str = amount_str.replace(",", "")

        try:
            return float(amount_str)
        except ValueError:
            return 0.0

    def _calculate_amount(self, row: pd.Series) -> float:
        """Calculate net amount from debit/credit or amount columns."""
        # If amount column exists
        if "amount" in row:
            amt = self._parse_amount(row["amount"])
            # Check if type indicates debit
            if "type" in row:
                txn_type = str(row["type"]).lower()
                if any(x in txn_type for x in ["debit", "dr", "withdrawal", "out"]):
                    return -abs(amt)
                elif any(x in txn_type for x in ["credit", "cr", "deposit", "in"]):
                    return abs(amt)
            return amt

        # Otherwise use debit/credit
        debit = self._parse_amount(row.get("debit", 0))
        credit = self._parse_amount(row.get("credit", 0))

        return credit - debit

    def _categorize_transaction(
        self, description: str, merchant: str, method: str
    ) -> str:
        """Categorize transaction based on description and merchant."""
        desc_lower = description.lower()

        # Category rules
        categories = {
            "Food & Dining": [
                "swiggy",
                "zomato",
                "food",
                "restaurant",
                "cafe",
                "pizza",
                "burger",
                "mcdonalds",
                "kfc",
                "dominos",
                "subway",
                "starbucks",
            ],
            "Transportation": [
                "uber",
                "ola",
                "rapido",
                "fuel",
                "petrol",
                "diesel",
                "transport",
                "irctc",
                "railway",
                "metro",
            ],
            "Shopping": [
                "amazon",
                "flipkart",
                "myntra",
                "ajio",
                "shopping",
                "retail",
                "mall",
                "store",
            ],
            "Groceries": [
                "blinkit",
                "zepto",
                "bigbasket",
                "grofers",
                "grocery",
                "supermarket",
                "dmart",
                "reliance fresh",
            ],
            "Entertainment": [
                "netflix",
                "spotify",
                "youtube",
                "prime",
                "hotstar",
                "movie",
                "entertainment",
                "disney",
            ],
            "Utilities": [
                "electricity",
                "water",
                "gas",
                "bill",
                "recharge",
                "jio",
                "airtel",
                "vodafone",
                "utility",
            ],
            "Health & Wellness": [
                "pharmacy",
                "medical",
                "health",
                "hospital",
                "clinic",
                "apollo",
            ],
            "Financial": [
                "emi",
                "loan",
                "insurance",
                "investment",
                "mutual fund",
                "sip",
            ],
            "Cash": ["atm", "cash", "withdrawal"],
            "Transfer": ["upi", "neft", "imps", "rtgs", "transfer"],
        }

        # Check merchant first
        merch_lower = merchant.lower()
        for category, keywords in categories.items():
            if any(kw in merch_lower for kw in keywords):
                return category

        # Check description
        for category, keywords in categories.items():
            if any(kw in desc_lower for kw in keywords):
                return category

        # Default category
        if method == "ATM":
            return "Cash"
        elif method in ["UPI", "NEFT", "IMPS"]:
            return "Transfer"

        return "Uncategorized"

    def parse(self) -> pd.DataFrame:
        """
        Parse the bank statement and return standardized DataFrame.

        Returns:
            DataFrame with columns: date, amount, description, type, category,
                                   merchant, method, entity, reference, location
        """
        logger.info("Reading file...")
        df = self._read_file()

        if df.empty:
            raise ValueError("File contains no data")

        logger.info(f"Read {len(df)} rows")

        # Find and set header row
        header_row = self._find_header_row(df)
        if header_row > 0:
            df.columns = df.iloc[header_row]
            df = df.iloc[header_row + 1 :].reset_index(drop=True)

        # Normalize columns
        df = self._normalize_columns(df)

        # Detect bank type
        detected_bank = self.detect_bank_type(df, list(df.columns))
        logger.info(f"Detected bank type: {detected_bank}")

        # Validate required columns
        if "date" not in df.columns:
            raise ValueError("Could not find date column")
        if "description" not in df.columns:
            raise ValueError("Could not find description column")
        if "amount" not in df.columns and (
            "debit" not in df.columns and "credit" not in df.columns
        ):
            raise ValueError("Could not find amount column (amount, debit, or credit)")

        # Parse transactions
        transactions = []
        progress = ProgressTracker(len(df), self.progress_callback)

        for idx, row in df.iterrows():
            try:
                # Parse date
                date = self._parse_date(row.get("date"))
                if not date:
                    continue

                # Calculate amount
                amount = self._calculate_amount(row)
                if amount == 0:
                    continue

                # Get description
                description = str(row.get("description", "")).strip()
                if not description:
                    continue

                # Extract structured info
                extracted = self.extractor.extract(description)

                # Determine merchant
                merchant = extracted.get("entity") or self.merchant_extractor.extract(
                    description
                )

                # Categorize
                category = self._categorize_transaction(
                    description, merchant, extracted.get("method", "")
                )

                # Create transaction
                txn = ParsedTransaction(
                    date=date,
                    amount=amount,
                    description=description,
                    transaction_type="debit" if amount < 0 else "credit",
                    category=category,
                    merchant=merchant,
                    method=extracted.get("method", ""),
                    entity=extracted.get("entity", ""),
                    reference=extracted.get("reference", ""),
                    location=extracted.get("location", ""),
                    raw_data=row.to_dict(),
                )

                transactions.append(txn.to_dict())

            except Exception as e:
                logger.warning(f"Error parsing row {idx}: {e}")
                continue

            progress.update()

        progress.finish()

        if not transactions:
            raise ValueError("No valid transactions found in file")

        result_df = pd.DataFrame(transactions)
        logger.info(f"Successfully parsed {len(result_df)} transactions")

        return result_df

    def parse_to_records(self) -> List[Dict[str, Any]]:
        """Parse and return as list of dictionaries."""
        df = self.parse()
        return df.to_dict("records")


def parse_bank_statement(
    file_path: Optional[str] = None,
    file_content: Optional[bytes] = None,
    bank_type: Optional[str] = None,
    password: Optional[str] = None,
    progress_callback: Optional[Callable] = None,
) -> pd.DataFrame:
    """
    Convenience function to parse a bank statement.

    Args:
        file_path: Path to the file
        file_content: File content as bytes
        bank_type: Bank type (hdfc, icici, sbi, axis, generic)
        password: Password for encrypted files
        progress_callback: Callback for progress updates

    Returns:
        DataFrame with parsed transactions
    """
    parser = BankStatementParser(
        file_path=file_path,
        file_content=file_content,
        bank_type=bank_type,
        password=password,
        progress_callback=progress_callback,
    )
    return parser.parse()
