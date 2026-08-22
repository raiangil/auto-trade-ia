import random

import requests
from datetime import datetime, timedelta
import pandas as pd

from src.config.settings import settings
MARKET_PHASES = {
    "bull": [
        ("2020-10-01", "2021-04-15"),
        ("2023-10-01", "2024-03-15"),
    ],
    "bear": [
        ("2021-11-15", "2022-11-20"),
    ],
    "sideways": [
        ("2022-12-01", "2023-03-15"),
        ("2024-03-20", "2024-09-01"),
    ],
    "high_volatility": [
        ("2020-03-01", "2020-04-30"),
        ("2021-05-01", "2021-06-30"),
        ("2022-05-01", "2022-07-01"),
    ],
}
MARKET_DATES = {
  "BTCUSDT": {
    "from": "2021-01-01", 
    "to": "2026-07-16"
  },
  "ETHUSDT": {
    "from": "2021-01-01", 
    "to": "2026-07-16"
  },
  "BNBUSDT": {
    "from": "2021-01-01", 
    "to": "2026-07-16"
  },
}

class MarketAnalysisService:
  def __init__(self):
    self.base_url = "https://fapi.binance.com"
    self.session = requests.Session()

  #region helpers
  def _public_request(self, endpoint: str, params: dict=None):
    url = f"{self.base_url}{endpoint}"
    response = self.session.get(
      url,
      params=params or {},
      timeout=10
    )
    try:
      data = response.json()
    except Exception:
      data = {"raw": response.text}
    if response.status_code >= 400:
      raise Exception(f"Binance public error {response.status_code}: {data}")
    return data

  def _last_valid(self, values):
    for value in reversed(values):
      if value is not None:
        return value
    return None
  
  def _convert_klines_to_dataframe(self, klines):
    columns = [
      "open_time", "open", "high", "low", "close", "volume",
      "close_time", "quote_volume", "number_of_trades",
      "taker_buy_base_volume", "taker_buy_quote_volume", "ignore"
    ]

    df = pd.DataFrame(klines, columns=columns)
    # Eliminar última vela porque puede estar abierta
    df = df.iloc[:-1].copy()
    
    df["open_time"] = pd.to_datetime(df["open_time"], unit='ms', utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit='ms', utc=True)
    numeric_cols = ["open", "high", "low", "close", "volume", "quote_volume", "taker_buy_base_volume", "taker_buy_quote_volume"]
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
    return df
  
  def _calculate_returns(self, df, periods):
    df = df.copy()
    for period in periods:
      df[f'return_{period}'] = df['close'].pct_change(periods=period) * 100
    return df
  
  def _get_trend_direction(self, row):
    if row['ema_20_above_50'] and row['ema_50_above_200']:
      return "bullish"
    
    if not row['ema_20_above_50'] and not row['ema_50_above_200']:
      return "bearish"
    
    return "sideways"

  def _calculate_ema_features(self, df, ema_periods):
    df = df.copy()
    for period in ema_periods:
      ema_col = f'ema_{period}'
      distance_col = f'ema_{period}_distance_pct'

      df[ema_col] = df['close'].ewm(span=period, adjust=False).mean()
      
      df[distance_col] = (df['close'] - df[ema_col]) / df[ema_col] * 100
    
    df['ema_20_above_50'] = df['ema_20'] > df['ema_50']
    df['ema_50_above_200'] = df['ema_50'] > df['ema_200']

    df['trend_direction'] = df.apply(self._get_trend_direction, axis=1)

    return df
  
  def _calculate_rsi(self, df, period=14):
    df = df.copy()

    delta = df['close'].diff()

    gain = (delta.clip(lower=0)).rolling(window=period).mean()
    loss = (-delta.clip(upper=0)).rolling(window=period).mean()

    rs = gain / loss
    df[f'rsi_{period}'] = 100 - (100 / (1 + rs))
    return df
  
  def _calculate_macd(self, df):
    df = df.copy()

    ema_12 = df['close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['close'].ewm(span=26, adjust=False).mean()

    df['macd_line'] = ema_12 - ema_26
    df['signal_line'] = df['macd_line'].ewm(span=9, adjust=False).mean()
    df['macd_histogram'] = df['macd_line'] - df['signal_line']

    return df
  
  def _calculate_momentum_features(self, df):
    df = df.copy()

    df = self._calculate_rsi(df)
    df = self._calculate_macd(df)
    return df
  
  def _calculate_candle_range_pct(self, df):
    df = df.copy()

    df['candle_range_pct'] = (df['high'] - df['low']) / df['low'] * 100
    
    return df
  
  def _calculate_atr_percent(self, df, period=14):
    df = df.copy()

    high_low = df['high'] - df['low']
    high_close_prev = (df['high'] - df['close'].shift(1)).abs()
    low_close_prev = (df['low'] - df['close'].shift(1)).abs()

    true_range = pd.concat(
      [high_low, high_close_prev, low_close_prev], 
      axis=1
    ).max(axis=1)

    atr = true_range.rolling(window=period).mean()
    df['atr_percent'] = atr / df['close'] * 100
    
    return df
  
  def _calculate_rolling_volatility(self, df, period=20):
    df = df.copy()

    returns = df['close'].pct_change()
    df[f'rolling_volatility_{period}'] = returns.rolling(window=period).std() * 100

    return df
  
  def _calculate_volatility_features(self, df):
    df = df.copy()

    df = self._calculate_candle_range_pct(df)
    df = self._calculate_atr_percent(df)
    df = self._calculate_rolling_volatility(df)

    return df
  
  def _calculate_relative_volume(self, df, period=20):
    df = df.copy()

    volume_sma = df['volume'].rolling(window=period).mean()
    df['relative_volume'] = df['volume'] / volume_sma

    return df
  
  def _calculate_volume_change(self, df, period=5):
    df = df.copy()

    df[f'volume_change_{period}'] = df['volume'].pct_change(periods=period) * 100

    return df
  
  def _calculate_volume_features(self, df):
    df = df.copy()

    df = self._calculate_relative_volume(df)
    df = self._calculate_volume_change(df)

    return df
  def _interval_to_minutes(self, interval):
    unit = interval[-1]
    value = int(interval[:-1])

    if unit == 'm':
      return value
    elif unit == 'h':
      return value * 60
    elif unit == 'd':
      return value * 60 * 24
    else:
      raise ValueError(f"Intervalo desconocido: {interval}")

  def _get_decision_time_from_market_phase(self, phase_name, interval):
    if phase_name not in MARKET_PHASES and phase_name != "random":
      raise ValueError(f"Fase de mercado desconocida: {phase_name}")

    if phase_name == "random":
      phase_name = random.choice(list(MARKET_PHASES.keys()))

    interval_minutes = self._interval_to_minutes(interval)
    phase_start_str, phase_end_str = MARKET_PHASES[phase_name][0]

    phase_start = datetime.strptime(phase_start_str, "%Y-%m-%d")
    phase_end = datetime.strptime(phase_end_str, "%Y-%m-%d")

    valid_start = phase_start + timedelta(minutes=interval_minutes * settings.indicator_lookback_limit)
    valid_end = phase_end

    random_seconds = random.randint(
        0,
        int((valid_end - valid_start).total_seconds())
    )
    decision_time = valid_start + timedelta(seconds=random_seconds)
    return decision_time
  def _get_decision_time_from_symbol(self, symbol, last_date: datetime = None, interval="1h"):
    if symbol not in MARKET_DATES:
      raise ValueError(f"Símbolo desconocido: {symbol}")

    if not last_date:
      return datetime.strptime(MARKET_DATES[symbol]["from"], "%Y-%m-%d")
    
    # print(f"Obteniendo próxima fecha de decisión para {symbol} intervalo {interval} después de {last_date.isoformat()}Z")
    decision_time = last_date + timedelta(minutes=self._interval_to_minutes(interval))  # asumiendo intervalo de 1 hora
    
    return decision_time
  #endregion helpers
  #region private methods
  def _get_klines_from_date(self, symbol, interval, start_date=None, limit=1000):
    """Obtiene klines desde una fecha específica. Si no se proporciona fecha, obtiene los klines más recientes.
      0  open_time                 = 1781902800000
      1  open                      = 63217.30
      2  high                      = 63253.60
      3  low                       = 63024.10
      4  close                     = 63048.00
      5  volume                    = 1954.973
      6  close_time                = 1781906399999
      7  quote_volume              = 123443316.92450
      8  number_of_trades          = 53651
      9  taker_buy_base_volume     = 982.408
      10 taker_buy_quote_volume    = 62031471.27150
      11 ignore  
    """
    start_time = int(start_date.timestamp() * 1000) if start_date else None
    endpoint = "/fapi/v1/klines"
    params = {
      "symbol": symbol,
      "interval": interval,
      "startTime": start_time,
      "limit": limit
    }

    klines = self._public_request(endpoint, params)
    return klines
  
  #endregion private methods
  #region public methods
  def get_current_price_symbol(self, symbol):
    """Obtiene el precio actual de un símbolo"""
    endpoint = "/fapi/v1/ticker/price"
    params = {"symbol": symbol}
    data = self._public_request(endpoint, params)
    return float(data.get("price", 0))

  def get_klines_from_date_df(self, symbol, interval, start_date=None, limit=1000):
    klines = self._get_klines_from_date(symbol, interval, start_date, limit)

    df = self._convert_klines_to_dataframe(klines)
    return df[:settings.indicator_lookback_limit].copy(), df[settings.indicator_lookback_limit:].copy()
  
  def calculate_symbol_indicators(self, klines_df):
    """Obtiene indicadores técnicos para un símbolo e intervalo desde una fecha específica. Si no se proporciona fecha, obtiene los datos más recientes.
      0  symbol                    = par analizado, ejemplo BTCUSDT
      1  timeframe                 = temporalidad, ejemplo 1h / 15m
      2  decision_time             = fecha/hora donde se toma la decisión
      3  decision_price            = precio exacto en el momento de decisión
      4  session_hour              = hora del día, ejemplo 14
      5  day_of_week               = día de la semana, ejemplo Monday
      6  lookback_candles          = cantidad de velas usadas hacia atrás para calcular contexto
      
      7  c_open                    = open de la vela actual
      8  c_high                    = high de la vela actual
      9  c_low                     = low de la vela actual
      10 c_close                   = close de la vela actual
      11 volume                    = volumen de la vela actual

      12 return_1                  = cambio % del precio en la última vela
      13 return_3                  = cambio % del precio en las últimas 3 velas
      14 return_5                  = cambio % del precio en las últimas 5 velas
      15 return_10                 = cambio % del precio en las últimas 10 velas
      16 return_20                 = cambio % del precio en las últimas 20 velas

      17 ema_9_distance_pct        = distancia % del precio actual a la EMA 9
      18 ema_20_distance_pct       = distancia % del precio actual a la EMA 20
      19 ema_50_distance_pct       = distancia % del precio actual a la EMA 50
      20 ema_100_distance_pct      = distancia % del precio actual a la EMA 100
      21 ema_200_distance_pct      = distancia % del precio actual a la EMA 200

      22 ema_20_above_50           = True si EMA 20 está arriba de EMA 50
      23 ema_50_above_200          = True si EMA 50 está arriba de EMA 200
      24 trend_direction           = tendencia resumida: bullish / bearish / sideways

      25 rsi_14                    = RSI de 14 periodos
      26 macd_histogram            = histograma MACD, mide momentum alcista/bajista

      27 atr_percent               = ATR expresado como % del precio
      28 candle_range_pct          = rango de la vela actual en %
      29 rolling_volatility_20     = volatilidad reciente de las últimas 20 velas

      30 relative_volume           = volumen actual dividido entre volumen promedio
      31 volume_change_5           = cambio % del volumen vs hace 5 velas
    """
    symbol_data_df = klines_df.copy()
    # len_df = len(symbol_data_df)
    numeric_cols = [
      "open", "high", "low", "close", "volume",
      "quote_volume", "taker_buy_base_volume", "taker_buy_quote_volume"
    ]
    existing_numeric_cols = [col for col in numeric_cols if col in symbol_data_df.columns]
    if existing_numeric_cols:
      symbol_data_df[existing_numeric_cols] = symbol_data_df[existing_numeric_cols].apply(pd.to_numeric, errors='coerce')

    symbol_data_df = self._calculate_returns(symbol_data_df, [1, 3, 5, 10, 20])
    symbol_data_df = self._calculate_ema_features(symbol_data_df, [9, 20, 50, 100, 200])
    symbol_data_df = self._calculate_momentum_features(symbol_data_df)
    symbol_data_df = self._calculate_volatility_features(symbol_data_df)
    symbol_data_df = self._calculate_volume_features(symbol_data_df)
    # symbol,timeframe,decision_time,decision_price,session_hour,day_of_week,lookback_candles,c_open,c_high,c_low,c_close,volume,return_1,return_3,return_5,return_10,return_20,ema_9_distance_pct,ema_20_distance_pct,ema_50_distance_pct,ema_100_distance_pct,ema_200_distance_pct,ema_20_above_50,ema_50_above_200,trend_direction,rsi_14,macd_histogram,atr_percent,candle_range_pct,rolling_volatility_20,relative_volume,volume_change_5
    
    return {
      "decision_time": self._last_valid(symbol_data_df['open_time']),
      "decision_price": float(self._last_valid(symbol_data_df["close"])),
      "session_hour": int(self._last_valid(symbol_data_df["open_time"].dt.hour)),
      "day_of_week": self._last_valid(symbol_data_df["open_time"].dt.strftime("%A")),
      "lookback_candles": len(symbol_data_df),
      "c_open": float(self._last_valid(symbol_data_df["open"])),
      "c_high": float(self._last_valid(symbol_data_df["high"])),
      "c_low": float(self._last_valid(symbol_data_df["low"])),
      "c_close": float(self._last_valid(symbol_data_df["close"])),
      "volume": float(self._last_valid(symbol_data_df["volume"])),
      "return_1": float(self._last_valid(symbol_data_df['return_1'])),
      "return_3": float(self._last_valid(symbol_data_df['return_3'])),
      "return_5": float(self._last_valid(symbol_data_df['return_5'])),
      "return_10": float(self._last_valid(symbol_data_df['return_10'])),
      "return_20": float(self._last_valid(symbol_data_df['return_20'])),
      "ema_9_distance_pct": float(self._last_valid(symbol_data_df["ema_9_distance_pct"])),
      "ema_20_distance_pct": float(self._last_valid(symbol_data_df["ema_20_distance_pct"])),
      "ema_50_distance_pct": float(self._last_valid(symbol_data_df["ema_50_distance_pct"])),
      "ema_100_distance_pct": float(self._last_valid(symbol_data_df["ema_100_distance_pct"])),
      "ema_200_distance_pct": float(self._last_valid(symbol_data_df["ema_200_distance_pct"])),
      "ema_20_above_50": bool(self._last_valid(symbol_data_df["ema_20_above_50"])),
      "ema_50_above_200": bool(self._last_valid(symbol_data_df["ema_50_above_200"])),
      "trend_direction": self._last_valid(symbol_data_df["trend_direction"]),
      "rsi_14": float(self._last_valid(symbol_data_df["rsi_14"])),
      "macd_histogram": float(self._last_valid(symbol_data_df["macd_histogram"])),
      "atr_percent": float(self._last_valid(symbol_data_df["atr_percent"])),
      "candle_range_pct": float(self._last_valid(symbol_data_df["candle_range_pct"])),
      "rolling_volatility_20": float(self._last_valid(symbol_data_df["rolling_volatility_20"])),
      "relative_volume": float(self._last_valid(symbol_data_df["relative_volume"])),
      "volume_change_5": float(self._last_valid(symbol_data_df["volume_change_5"]))
    }

  # def get_symbol_klines_df_from_market_phase(self, symbol, interval):
  #   decision_time = self._get_decision_time_from_market_phase(phase_name, interval)
  #   limit = settings.indicator_lookback_limit + settings.indicator_future_limit
  #   klines_df = self._get_klines_from_date_df(symbol, interval, decision_time, limit=limit)


  #   return klines_df[:settings.indicator_lookback_limit].copy(), klines_df[settings.indicator_lookback_limit:].copy()
  def calculate_result_dataset_1(self,dataset, future_klines_df):
    future_klines_df = future_klines_df.copy()

    target_time = dataset.decision_time + timedelta(minutes=settings.max_minutes_to_target)

    target_action = None
    row_time = None
    row_pos = None
    for index, row in future_klines_df.iterrows():
      row_pos = index
      if row["high"] >= dataset.decision_price * (1 + settings.target_move_pct / 100):
        target_action = "BUY"
        row_time = row["open_time"]
        break
      if row["low"] <= dataset.decision_price * (1 - settings.target_move_pct / 100):
        target_action = "SELL"
        row_time = row["open_time"]
        break

    return {
      "dataset_id": dataset.id,
      "candles_to_close": row_pos-settings.indicator_lookback_limit if row_pos is not None else None, 
      "decision": target_action if row_time and row_time <= target_time else "SKIP",
      "target_action": target_action,
      "date_to_close": row_time if target_action else None,
    }
  
  def calculate_result_dataset(self, dataset, future_klines_df):
    future_klines_df = (
      future_klines_df.copy()
      .sort_values("open_time")
      .reset_index(drop=True)
    )
  
    entry_price = dataset.decision_price
  
    take_profit_pct = 2.0
    stop_loss_pct = 0.67
  
    # Niveles de la operación LONG
    long_take_profit = entry_price * (1 + take_profit_pct / 100)
    long_stop_loss = entry_price * (1 - stop_loss_pct / 100)
  
    # Niveles de la operación SHORT
    short_take_profit = entry_price * (1 - take_profit_pct / 100)
    short_stop_loss = entry_price * (1 + stop_loss_pct / 100)
  
    long_status = "OPEN"
    short_status = "OPEN"
  
    for candle_number, row in future_klines_df.iterrows():
      high = float(row["high"])
      low = float(row["low"])
      row_time = row["open_time"]
  
      # Evaluar LONG
      if long_status == "OPEN":
        long_hit_stop = low <= long_stop_loss
        long_hit_target = high >= long_take_profit
  
        # Conservador: si TP y SL ocurren en la misma vela,
        # se considera que llegó primero al stop.
        if long_hit_stop:
          long_status = "STOP_LOSS"
  
        elif long_hit_target:
          return {
            "dataset_id": dataset.id,
            "candles_to_close": candle_number + 1,
            "decision": "BUY",
            "target_action": "BUY",
            "date_to_close": row_time,
          }
  
      # Evaluar SHORT
      if short_status == "OPEN":
        short_hit_stop = high >= short_stop_loss
        short_hit_target = low <= short_take_profit
  
        if short_hit_stop:
          short_status = "STOP_LOSS"
  
        elif short_hit_target:
          return {
            "dataset_id": dataset.id,
            "candles_to_close": candle_number + 1,
            "decision": "SELL",
            "target_action": "SELL",
            "date_to_close": row_time,
          }
  
      # Las dos opciones llegaron primero al stop
      if long_status == "STOP_LOSS" and short_status == "STOP_LOSS":
        return {
          "dataset_id": dataset.id,
          "candles_to_close": candle_number + 1,
          "decision": "SKIP",
          "target_action": None,
          "date_to_close": row_time,
        }
  
    # Se terminaron las velas y ninguna operación llegó al TP
    return {
      "dataset_id": dataset.id,
      "candles_to_close": None,
      "decision": "SKIP",
      "target_action": None,
      "date_to_close": None,
    }
    #endregion public methods