import os
import joblib
import pandas as pd

SYMBOL_ORDER = {
  "BTCUSDT": 1,
  "ETHUSDT": 2,
  "BNBUSDT": 3
}

TIMEFRAME_ORDER = {
  "1m": 1,
  "5m": 2,
  "15m": 3,
  "30m": 4,
  "1h": 5,
  "4h": 6,
  "1d": 7
}

DAY_OF_WEEK_ORDER = {
  "Monday": 1,
  "Tuesday": 2,
  "Wednesday": 3,
  "Thursday": 4,
  "Friday": 5,
  "Saturday": 6,
  "Sunday": 7
}

TREND_DIRECTION_ORDER = {
  "bearish": 1,
  "sideways": 2,
  "bullish": 3
}

DECISION_ORDER = [
  "SKIP",
  "SELL",
  "BUY"
]

class ModelService():
  def __init__(self, model_path: str):
    self.model = self._load_model(model_path)

  def _load_model(self, model_path: str):
    if not os.path.exists(model_path):
      raise FileNotFoundError(f"El archivo del modelo no existe: {model_path}")
    
    model = joblib.load(model_path)
    print(f"Modelo cargado desde: {model_path}")
    return model
  
  def format_indicator(self, indicator):
    formatted_indicator = indicator.copy()

    formatted_indicator["symbol_order"] = SYMBOL_ORDER.get(
      formatted_indicator.pop("symbol"),
      0
    )

    formatted_indicator["timeframe_order"] = TIMEFRAME_ORDER.get(
      formatted_indicator.pop("timeframe"),
      0
    )

    formatted_indicator["decision_time_timestamp"] = int(
      pd.to_datetime(
        formatted_indicator.pop("decision_time"),
        utc=True
      ).timestamp()
    )

    formatted_indicator["day_of_week_order"] = DAY_OF_WEEK_ORDER.get(
      formatted_indicator.pop("day_of_week"),
      0
    )

    formatted_indicator["ema_20_above_50_order"] = int(
      formatted_indicator.pop("ema_20_above_50")
    )

    formatted_indicator["ema_50_above_200_order"] = int(
      formatted_indicator.pop("ema_50_above_200")
    )

    formatted_indicator["trend_direction_order"] = TREND_DIRECTION_ORDER.get(
      formatted_indicator.pop("trend_direction"),
      0
    )

    return formatted_indicator

  def _format_sample(self, sample: dict):
    formatted_indicator = sample.copy()

    formatted_indicator["symbol_order"] = SYMBOL_ORDER.get(
      formatted_indicator.pop("symbol"),
      0
    )

    formatted_indicator["timeframe_order"] = TIMEFRAME_ORDER.get(
      formatted_indicator.pop("timeframe"),
      0
    )

    formatted_indicator["decision_time_timestamp"] = int(
      pd.to_datetime(
        formatted_indicator.pop("decision_time"),
        utc=True
      ).timestamp()
    )

    formatted_indicator["day_of_week_order"] = DAY_OF_WEEK_ORDER.get(
      formatted_indicator.pop("day_of_week"),
      0
    )

    formatted_indicator["ema_20_above_50_order"] = int(
      formatted_indicator.pop("ema_20_above_50")
    )

    formatted_indicator["ema_50_above_200_order"] = int(
      formatted_indicator.pop("ema_50_above_200")
    )

    formatted_indicator["trend_direction_order"] = TREND_DIRECTION_ORDER.get(
      formatted_indicator.pop("trend_direction"),
      0
    )
    # Convertir el diccionario a un DataFrame de una sola fila
    df = pd.DataFrame([formatted_indicator])
    columns_order = [
      "symbol_order",
      "timeframe_order",
      "decision_time_timestamp",
      "decision_price",
      "session_hour",
      "day_of_week_order",
      "lookback_candles",
      "c_open",
      "c_high",
      "c_low",
      "c_close",
      "volume",
      "return_1",
      "return_3",
      "return_5",
      "return_10",
      "return_20",
      "ema_9_distance_pct",
      "ema_20_distance_pct",
      "ema_50_distance_pct",
      "ema_100_distance_pct",
      "ema_200_distance_pct",
      "ema_20_above_50_order",
      "ema_50_above_200_order",
      "trend_direction_order",
      "rsi_14",
      "macd_histogram",
      "atr_percent",
      "candle_range_pct",
      "rolling_volatility_20",
      "relative_volume",
      "volume_change_5"
    ]
    df = df.reindex(columns=columns_order)
    return df

  def predict(self, sample: dict):
    X = self._format_sample(sample)
    prediction = self.model.predict(X)[0]
    probabilities = [round(p, 2) for p in self.model.predict_proba(X)[0]]
    return prediction, probabilities
  
