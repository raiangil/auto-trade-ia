import os
import joblib
import pandas as pd

SYMBOL_ORDER = {"BTCUSDT": 1, "ETHUSDT": 2, "BNBUSDT": 3}
TIMEFRAME_ORDER = {"1m": 1, "5m": 2, "15m": 3, "30m": 4, "1h": 5, "4h": 6, "1d": 7}
DAY_OF_WEEK_ORDER = {"Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4, "Friday": 5, "Saturday": 6, "Sunday": 7}

FEATURES = [
  "symbol_order", "timeframe_order", "session_hour", "day_of_week_order",
  "return_1", "return_5", "return_20", "ema_9_distance_pct", "ema_50_distance_pct",
  "ema_200_distance_pct", "rsi_14", "macd_histogram", "atr_percent",
  "candle_range_pct", "rolling_volatility_20", "relative_volume", "volume_change_5"
]

class ModelService:
  def __init__(self, model_path: str):
    self.model = joblib.load(model_path)

  def _format_sample(self, sample: dict) -> pd.DataFrame:
    f = {
      "symbol_order": SYMBOL_ORDER.get(sample.get("symbol"), 0),
      "timeframe_order": TIMEFRAME_ORDER.get(sample.get("timeframe"), 0),
      "session_hour": sample.get("session_hour"),
      "day_of_week_order": DAY_OF_WEEK_ORDER.get(sample.get("day_of_week"), 0),
      "return_1": sample.get("return_1"),
      "return_5": sample.get("return_5"),
      "return_20": sample.get("return_20"),
      "ema_9_distance_pct": sample.get("ema_9_distance_pct"),
      "ema_50_distance_pct": sample.get("ema_50_distance_pct"),
      "ema_200_distance_pct": sample.get("ema_200_distance_pct"),
      "rsi_14": sample.get("rsi_14"),
      "macd_histogram": sample.get("macd_histogram"),
      "atr_percent": sample.get("atr_percent"),
      "candle_range_pct": sample.get("candle_range_pct"),
      "rolling_volatility_20": sample.get("rolling_volatility_20"),
      "relative_volume": sample.get("relative_volume"),
      "volume_change_5": sample.get("volume_change_5"),
    }
    return pd.DataFrame([f]).reindex(columns=FEATURES)

  def predict(self, sample: dict):
    X = self._format_sample(sample)
    pred = self.model.predict(X)[0]
    probs = [round(p, 4) for p in self.model.predict_proba(X)[0]]
    return pred, probs
  
