"""
SCALE Ingestion Engine

Transaction data ingestion, parsing, and normalization.
"""

__version__ = "0.1.0"

from .merchant_extractor import MerchantExtractor
from .parser import BankStatementParser, ParsedTransaction, parse_bank_statement

__all__ = [
    "BankStatementParser",
    "parse_bank_statement",
    "ParsedTransaction",
    "MerchantExtractor",
]
