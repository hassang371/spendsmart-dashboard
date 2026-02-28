import pandas as pd
from packages.forecasting.dataset import TransactionLoader


def test_aggregate_daily_basics():
    # 1. Setup dummy data
    data = {
        "date": ["2026-01-01", "2026-01-01", "2026-01-02", "2026-01-04"],
        "amount": [-50.00, -20.00, 1000.00, -10.00],
        "merchant": ["Walmart", "Uber", "Salary", "Coffee"],
    }
    df = pd.DataFrame(data)

    # 2. Initialize Loader
    loader = TransactionLoader(df)

    # 3. Aggregate
    daily_df = loader.aggregate_daily()

    # 4. Assertions
    assert "daily_spend" in daily_df.columns
    assert "daily_income" in daily_df.columns
    assert "closing_balance" in daily_df.columns

    # Check Jan 1st aggregation
    jan_1 = daily_df.loc["2026-01-01"]
    assert jan_1["daily_spend"] == 70.00  # 50 + 20
    assert jan_1["daily_income"] == 0.00

    # Check Jan 2nd (Income)
    jan_2 = daily_df.loc["2026-01-02"]
    assert jan_2["daily_income"] == 1000.00
    assert jan_2["daily_spend"] == 0.00

    # Check Jan 3rd (Missing date filling)
    jan_3 = daily_df.loc["2026-01-03"]
    assert jan_3["daily_spend"] == 0.00
    assert jan_3["daily_income"] == 0.00
