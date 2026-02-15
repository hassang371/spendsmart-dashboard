import re
import random
from typing import List, Dict
from collections import Counter


class TextAugmenter:
    """
    Text augmentation for contrastive learning.
    Implements Inverse Frequency Dropout and Substring Sampling per HypCD paper.
    """

    def __init__(self, texts: List[str]):
        """
        Initialize with corpus to compute term frequencies.

        Args:
            texts: List of text strings for computing term frequencies
        """
        self.term_freq = self._compute_tf(texts)

    def _compute_tf(self, texts: List[str]) -> Dict[str, float]:
        """Compute normalized term frequencies across corpus."""
        if not texts:
            return {}

        # Tokenize and count
        all_tokens = []
        for text in texts:
            tokens = text.lower().split()
            all_tokens.extend(tokens)

        counts = Counter(all_tokens)
        max_count = max(counts.values()) if counts else 1

        # Normalize to [0, 1]
        return {term: count / max_count for term, count in counts.items()}

    def inverse_frequency_dropout(self, text: str, drop_prob: float = 0.3) -> str:
        """
        Mask frequent tokens with higher probability.

        Per Section 3.3.2: Dropout probability proportional to term frequency.

        Args:
            text: Input text
            drop_prob: Base dropout probability

        Returns:
            Augmented text with some tokens masked
        """
        tokens = text.split()
        masked = []

        for token in tokens:
            # Higher frequency = higher dropout probability
            tf = self.term_freq.get(token.lower(), 0.5)
            actual_drop_prob = drop_prob * tf

            if random.random() > actual_drop_prob:
                masked.append(token)

        return " ".join(masked) if masked else text

    def substring_sampling(self, text: str) -> str:
        """
        Create view by sampling substring.

        Per Section 3.3.2: Sample contiguous word sequence.

        Args:
            text: Input text

        Returns:
            Substring of original text
        """
        words = text.split()
        if len(words) <= 3:
            return text

        # Sample start and end indices
        start = random.randint(0, len(words) - 3)
        end = random.randint(start + 2, len(words))

        return " ".join(words[start:end])


def clean_description(text: str) -> str:
    """
    Cleans transaction descriptions by removing common noise patterns
    like UPI IDs, POS numbers, dates, and generic payment terms.
    """
    if not text:
        return ""

    # Normalize
    text = text.upper()

    # NEW: Standardize separators (*, -, _) → space
    text = re.sub(r"[*\-_]", " ", text)

    # 1. Remove UPI Handles (e.g., john@okicici, 9876543210@paytm)
    text = re.sub(r"[\w\.-]+@[\w\.-]+", "", text)

    # 2. Remove "UPI/" prefix and reference numbers (e.g., UPI/123456789/Ref...)
    text = re.sub(r"UPI(?:-|\/)?\d+[\w]*", "", text)
    text = re.sub(r"UPI\s*-?", "", text)

    # 3. Remove POS / ECOM / ATM indicators
    text = re.sub(r"\b(POS|ECOM|ATM|MPS|IMPS|NEFT|RTGS|ACH|MBk|WDL)\b", "", text)

    # 4. Remove Dates (DD-MM-YYYY, DD/MM, etc.) - diverse formats
    text = re.sub(r"\d{2}[-\/]\d{2}[-\/]\d{2,4}", "", text)
    text = re.sub(r"\d{2}[A-Z]{3}", "", text)  # 12JAN

    # 5. Remove pure number sequences (Order IDs, Ref nums) > 3 digits
    text = re.sub(r"\b\d{4,}\b", "", text)

    # 6. Remove generic words
    text = re.sub(
        r"\b(TXN|REF|ID|NO|TRANSFER|PAYMENT|TO|BY|FROM|BILL|IN|VIA)\b", "", text
    )

    # 7. Remove special characters and extra spaces
    text = re.sub(r"[^A-Z\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text
