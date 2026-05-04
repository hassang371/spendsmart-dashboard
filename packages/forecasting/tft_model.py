from pytorch_forecasting import TemporalFusionTransformer, TimeSeriesDataSet
from pytorch_forecasting.metrics import QuantileLoss


def create_tft_model(
    training_dataset: TimeSeriesDataSet,
    learning_rate=0.03,
    hidden_size=128,
    attention_head_size=8,
    dropout=0.1,
    hidden_continuous_size=64,
    lstm_layers=3,
    weight_decay: float = 0.0,
):
    """
    Creates a TemporalFusionTransformer model from the training dataset.

    Default hyperparameters per RFC-005 §"TFT hyperparameter supersession":
    ``hidden_size=128``, ``attention_head_size=8``, ``lstm_layers=3``,
    ``hidden_continuous_size=64``. The 12-bucket panel produces ~12× more
    rows per user than the v0 single-series schema, justifying the
    capacity bump.

    ``weight_decay`` (RFC-006) defaults to 0.0 (no L2) to preserve the
    current production codepath. The harness passes 1e-4 for the
    ``GROKKING`` regime.
    """
    tft = TemporalFusionTransformer.from_dataset(
        training_dataset,
        learning_rate=learning_rate,
        hidden_size=hidden_size,
        attention_head_size=attention_head_size,
        dropout=dropout,
        hidden_continuous_size=hidden_continuous_size,
        output_size=7,  # 7 quantiles by default for QuantileLoss
        loss=QuantileLoss(),
        log_interval=10,  # log example every 10 batches
        reduce_on_plateau_patience=4,
        lstm_layers=lstm_layers,
        weight_decay=weight_decay,
    )
    return tft
