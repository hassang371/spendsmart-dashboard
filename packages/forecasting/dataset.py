import pandas as pd
import numpy as np
from sklearn.preprocessing import RobustScaler
from pytorch_forecasting import TimeSeriesDataSet


class TimeScalar:
    def __init__(self, column="amount", quantile_range=(25.0, 75.0)):
        """
        RobustScaler wrapper for a specific column.
        Scales data using statistics that are robust to outliers.
        """
        self.column = column
        self.scaler = RobustScaler(quantile_range=quantile_range)

    def fit(self, df: pd.DataFrame):
        if self.column not in df.columns:
            raise KeyError(f"Column '{self.column}' not found in DataFrame")

        # Reshape for sklearn (n_samples, n_features)
        data = df[[self.column]].values
        self.scaler.fit(data)
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.column not in df.columns:
            raise KeyError(f"Column '{self.column}' not found in DataFrame")

        df_scaled = df.copy()
        data = df[[self.column]].values
        scaled_values = self.scaler.transform(data)
        df_scaled[self.column] = scaled_values.flatten()
        return df_scaled

    def inverse_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.column not in df.columns:
            raise KeyError(f"Column '{self.column}' not found in DataFrame")

        df_inv = df.copy()
        data = df[[self.column]].values
        inv_values = self.scaler.inverse_transform(data)
        df_inv[self.column] = inv_values.flatten()
        return df_inv


class TransactionLoader:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        # Ensure date is datetime
        if "date" in self.df.columns:
            self.df["date"] = pd.to_datetime(self.df["date"])

    def aggregate_daily(self, start_date=None, end_date=None) -> pd.DataFrame:
        """
        Aggregates transactions into daily summaries.
        Returns DataFrame with index 'date' and columns:
        - daily_spend: positive float (sum of absolute negative transactions)
        - daily_income: positive float (sum of positive transactions)
        - closing_balance: cumulative sum of (income - spend)
        """
        df = self.df.copy()

        # Filter date range
        if start_date:
            df = df[df["date"] >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df["date"] <= pd.to_datetime(end_date)]

        # Set index to date for resampling
        df.set_index("date", inplace=True)

        # Calculate Income and Spend
        # Income: Amount > 0
        # Spend: Amount < 0 (sum absolute)

        # Separate dataframes
        income_series = df[df["amount"] > 0]["amount"].resample("D").sum()
        spend_series = df[df["amount"] < 0]["amount"].resample("D").sum().abs()

        # Recombine
        daily_df = pd.DataFrame(
            {"daily_income": income_series, "daily_spend": spend_series}
        )

        # Fill NaNs from resampling (days with no transactions)
        daily_df.fillna(0.0, inplace=True)

        # Ensure all days in range are present
        if start_date and end_date:
            idx = pd.date_range(start_date, end_date)
            # Reindex introduces NaNs for new rows, fill with 0
            daily_df = daily_df.reindex(idx, fill_value=0.0)

        # Calculate Closing Balance (Cumulative Sum)
        # Net change = Income - Spend
        daily_df["net_change"] = daily_df["daily_income"] - daily_df["daily_spend"]
        daily_df["closing_balance"] = daily_df["net_change"].cumsum()

        # Drop temp column
        daily_df.drop(columns=["net_change"], inplace=True)
        date_col_name = daily_df.index.name or "date"

        # Ensure index name is preserved (it might be None after reindex if idx has no name)
        daily_df.index.name = "date"

        return daily_df

    def enrich_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Adds derived time features needed for TFT:
        - time_idx: monotonic integer index
        - day_of_week: 0-6
        - day_of_month: 1-31
        - group_id: constant 'main_user'
        """
        df = df.copy()

        # Ensure date is a column, not index
        if df.index.name == "date":
            df.reset_index(inplace=True)

        # Add time index (assuming sorted by date)
        df.sort_values("date", inplace=True)
        df["time_idx"] = np.arange(len(df))

        # Date parts
        df["day_of_week"] = df["date"].dt.dayofweek.astype(str).astype("category")
        df["day_of_month"] = df["date"].dt.day.astype(str).astype("category")

        # Group ID required by TFT
        df["group_id"] = "main_user"

        return df


def create_timeseries_dataset(
    data: pd.DataFrame, max_encoder_length=30, max_prediction_length=7
):
    """
    Creates a TimeSeriesDataSet for TFT training.
    Automatically includes ``is_payday`` as a known categorical when present.
    """
    known_categoricals = ["day_of_week", "day_of_month"]
    if "is_payday" in data.columns:
        known_categoricals.append("is_payday")

    return TimeSeriesDataSet(
        data,
        time_idx="time_idx",
        target="closing_balance",
        group_ids=["group_id"],
        min_encoder_length=max_encoder_length // 2,
        max_encoder_length=max_encoder_length,
        min_prediction_length=1,
        max_prediction_length=max_prediction_length,
        static_categoricals=["group_id"],
        time_varying_known_categoricals=known_categoricals,
        time_varying_known_reals=["time_idx", "daily_income", "daily_spend"],
        time_varying_unknown_reals=["closing_balance"],
        add_relative_time_idx=True,
        add_target_scales=True,
        add_encoder_length=True,
    )


def prepare_training_data(
    transactions: pd.DataFrame,
    start_date=None,
    end_date=None,
) -> pd.DataFrame:
    """Prepare enriched daily data used by forecasting training."""
    loader = TransactionLoader(transactions)
    daily = loader.aggregate_daily(start_date=start_date, end_date=end_date)
    return loader.enrich_features(daily)
