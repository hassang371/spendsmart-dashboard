import pandas as pd
import numpy as np
import pytest
from packages.forecasting.dataset import TimeScalar


def test_timescalar_robust_scaling():
    # Create data with outliers (typical transaction data)
    data = pd.DataFrame({"amount": [10.0, 12.0, 11.0, 10.5, 1000.0]})  # 1000 is outlier

    scaler = TimeScalar(column="amount")
    scaler.fit(data)

    scaled_data = scaler.transform(data)

    # Check scaling
    # Median of [10, 10.5, 11, 12, 1000] is 11.0
    # So 11.0 should become 0.0
    assert np.isclose(scaled_data["amount"].iloc[2], 0.0, atol=1e-5)

    # Check inverse transform
    original_data = scaler.inverse_transform(scaled_data)
    assert np.allclose(original_data["amount"], data["amount"])


def test_timescalar_unknown_column():
    data = pd.DataFrame({"val": [1, 2, 3]})
    scaler = TimeScalar(column="amount")
    with pytest.raises(KeyError):
        scaler.fit(data)
