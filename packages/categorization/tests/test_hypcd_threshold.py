from packages.categorization.hypcd import CONFIDENCE_THRESHOLD


def test_confidence_threshold_exists():
    assert isinstance(CONFIDENCE_THRESHOLD, float)
    assert 0.5 < CONFIDENCE_THRESHOLD <= 1.0


def test_confidence_threshold_default_is_ninety_percent():
    assert CONFIDENCE_THRESHOLD == 0.90
