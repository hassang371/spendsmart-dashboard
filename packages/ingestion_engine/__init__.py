"""
SCALE Ingestion Engine

Transaction data ingestion, parsing, and normalization.
"""

__version__ = "0.1.0"

from .parser import BankStatementParser, parse_bank_statement, ParsedTransaction
from .merchant_extractor import MerchantExtractor

__all__ = [
    "BankStatementParser",
    "parse_bank_statement",
    "ParsedTransaction",
    "MerchantExtractor",
]
