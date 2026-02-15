from pytorch_forecasting import TemporalFusionTransformer, TimeSeriesDataSet
from pytorch_forecasting.metrics import QuantileLoss


def create_tft_model(
    training_dataset: TimeSeriesDataSet,
    learning_rate=0.03,
    hidden_size=16,
    attention_head_size=1,
    dropout=0.1,
    hidden_continuous_size=8,
    lstm_layers=1,
):
    """
    Creates a TemporalFusionTransformer model from the training dataset.
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
    )
    return tft
