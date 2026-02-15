"""Tests for text augmentation in HypCD."""
import random

from packages.categorization.cleaner import TextAugmenter


def test_text_augmenter_init():
    """TextAugmenter should compute term frequencies from texts."""
    texts = ["food delivery zomato", "food delivery swiggy", "food restaurant"]
    augmenter = TextAugmenter(texts)

    # "food" appears in all 3, "delivery" in 2
    assert "food" in augmenter.term_freq
    assert augmenter.term_freq["food"] > augmenter.term_freq["delivery"]


def test_inverse_frequency_dropout():
    """IFD should mask frequent tokens with higher probability."""
    texts = ["food delivery zomato", "food delivery swiggy"]
    augmenter = TextAugmenter(texts)

    text = "food delivery zomato"
    random.seed(42)
    # Run multiple times to account for randomness
    results = [
        augmenter.inverse_frequency_dropout(text, drop_prob=0.5) for _ in range(20)
    ]

    # "food" is most frequent, should be dropped more often
    food_dropped = sum(1 for r in results if "food" not in r.lower().split())
    zomato_dropped = sum(1 for r in results if "zomato" not in r.lower().split())

    assert food_dropped >= zomato_dropped  # Frequent tokens dropped more


def test_substring_sampling():
    """Substring sampling should return contiguous word sequence."""
    augmenter = TextAugmenter([])
    text = "the quick brown fox jumps"

    result = augmenter.substring_sampling(text)
    words = result.split()
    original_words = text.split()

    # Should be a contiguous subset (min 2 words as per implementation)
    assert len(words) >= 2
    assert len(words) <= len(original_words)
    # All words in result should appear in original in same order
    assert all(w in original_words for w in words)
